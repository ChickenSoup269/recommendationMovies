import sys
import pandas as pd
import json
import requests
import os
from pymongo import MongoClient
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
load_dotenv()

# Hàm lấy danh sách thể loại từ API của TMDB
def get_genre_mapping(api_key):
    url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        genres = response.json().get("genres", [])
        genre_mapping = {genre["id"]: genre["name"] for genre in genres}
        return genre_mapping
    else:
        print(f"Error fetching genres from TMDB: {response.status_code}", file=sys.stderr)
        sys.exit(1)

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
genre_mapping = get_genre_mapping(TMDB_API_KEY)

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["test"]

users = list(db["users"].find())
bookings = list(db["bookings"].find())
movies = list(db["movies"].find())

# Chuyển _id thành chuỗi
for user in users:
    if "_id" in user:
        user["_id"] = str(user["_id"])
for booking in bookings:
    if "_id" in booking:
        booking["_id"] = str(booking["_id"])
    if "userId" in booking:
        booking["userId"] = str(booking["userId"])
for movie in movies:
    if "_id" in movie:
        movie["_id"] = str(movie["_id"])

# Tạo DataFrame
users_df = pd.DataFrame(users)
bookings_df = pd.DataFrame(bookings)
movies_df = pd.DataFrame(movies)

duplicate_columns = movies_df.columns[movies_df.columns.duplicated()]
if not duplicate_columns.empty:
    print(f"Warning: Found duplicate columns in movies_df before processing: {duplicate_columns}. Keeping the last one.", file=sys.stderr)
    movies_df = movies_df.loc[:, ~movies_df.columns.duplicated(keep='last')]

bookings_with_movies = bookings_df.merge(movies_df, left_on="movieId", right_on="tmdbId", suffixes=("", "_movie"))
user_bookings = bookings_with_movies.merge(users_df, left_on="userId", right_on="_id", suffixes=("", "_user"))

if user_bookings.empty:
    print("Warning: user_bookings is empty. Check if movieId or userId match across collections.", file=sys.stderr)
    sys.exit(1)

user_bookings["genre"] = user_bookings["genreIds"].apply(lambda ids: [genre_mapping.get(id, "Unknown") for id in ids])

user_genre_data = user_bookings[["userId", "movieId", "genre"]].copy()

all_genres = set(user_bookings["genre"].explode().unique()) | set(movies_df["genreIds"].explode().apply(lambda id: genre_mapping.get(id, "Unknown")).unique())
all_genres.discard("Unknown")
all_genres = sorted(all_genres)

for genre in all_genres:
    user_genre_data[genre] = user_genre_data["genre"].apply(lambda x: 1 if genre in x else 0)

user_genre_data = user_genre_data.drop(columns=["genre"])

user_profiles = user_genre_data.groupby("userId").sum()
user_profiles = user_profiles.drop(columns=["movieId"], errors="ignore")
user_profiles = user_profiles.div(user_profiles.sum(axis=1), axis=0).fillna(0)

# Tạo ma trận thể loại cho phim
movies_genres = movies_df[["_id"]].copy()
movies_df["genre"] = movies_df["genreIds"].apply(lambda ids: [genre_mapping.get(id, "Unknown") for id in ids])
for genre in all_genres:
    movies_genres[genre] = movies_df["genre"].apply(lambda x: 1 if genre in x else 0)
movies_genres.set_index("_id", inplace=True)

# Đường dẫn thư mục data ở cấp gốc
data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# Lưu dữ liệu đã huấn luyện
if user_profiles.empty:
    print("Warning: user_profiles is empty, not saving!", file=sys.stderr)
else:
    user_profiles.to_pickle(os.path.join(data_dir, "user_profiles.pkl"))
    print(f"Saved user_profiles.pkl to {data_dir}", file=sys.stderr)

if movies_genres.empty:
    print("Warning: movies_genres is empty, not saving!", file=sys.stderr)
else:
    movies_genres.to_pickle(os.path.join(data_dir, "movies_genres.pkl"))
    print(f"Saved movies_genres.pkl to {data_dir}", file=sys.stderr)

if movies_df.empty:
    print("Warning: movies_df is empty, not saving!", file=sys.stderr)
else:
    movies_df.to_pickle(os.path.join(data_dir, "movies_df.pkl"))
    print(f"Saved movies_df.pkl to {data_dir}", file=sys.stderr)

# Hàm gợi ý phim
def recommend_movies(user_id, user_profiles, movies_genres, movies_df):
    try:
        # Kiểm tra và loại bỏ cột trùng lặp trong movies_df sau khi đọc từ pickle
        duplicate_columns = movies_df.columns[movies_df.columns.duplicated()]
        if not duplicate_columns.empty:
            print(f"Warning: Found duplicate columns in movies_df after loading: {duplicate_columns}. Keeping the last one.", file=sys.stderr)
            movies_df = movies_df.loc[:, ~movies_df.columns.duplicated(keep='last')]

        movie_fields = [
            "_id", "tmdbId", "title", "originalTitle", "overview", "posterPath",
            "backdropPath", "genreIds", "releaseDate", "voteAverage", "voteCount",
            "popularity", "originalLanguage", "adult", "video", "status", "activePeriod"
        ]

        for field in movie_fields:
            if field not in movies_df.columns:
                movies_df[field] = None

        # Chuyển đổi activePeriod thành chuỗi nếu tồn tại
        if "activePeriod" in movies_df.columns:
            movies_df["activePeriod"] = movies_df["activePeriod"].apply(
                lambda x: {
                    "start": x["start"].strftime('%Y-%m-%d %H:%M:%S') if x and "start" in x and pd.notna(x["start"]) else None,
                    "end": x["end"].strftime('%Y-%m-%d %H:%M:%S') if x and "end" in x and pd.notna(x["end"]) else None
                } if isinstance(x, dict) else None
            )

        if user_id not in user_profiles.index:
            # Nếu người dùng không có lịch sử, trả về tất cả phim, sắp xếp theo popularity
            movies = movies_df[movie_fields].copy()
            movies["match_count"] = 0
            movies["similarity"] = 0.0
            movies = movies.sort_values(by="popularity", ascending=False)
            # Chuyển đổi cột datetime thành chuỗi trước khi trả về
            for col in ['releaseDate']:
                if col in movies.columns:
                    movies[col] = movies[col].astype(str)
            return movies[movie_fields + ["match_count", "similarity"]].to_dict(orient="records")

        # Lấy các thể loại ưu tiên của người dùng (các thể loại có giá trị > 0)
        user_profile = user_profiles.loc[user_id]
        preferred_genres = user_profile[user_profile > 0].index.tolist()
        if not preferred_genres:
            # Nếu không có thể loại ưu tiên, trả về tất cả phim, sắp xếp theo popularity
            movies = movies_df[movie_fields].copy()
            movies["match_count"] = 0
            movies["similarity"] = 0.0
            movies = movies.sort_values(by="popularity", ascending=False)
            # Chuyển đổi cột datetime thành chuỗi trước khi trả về
            for col in ['releaseDate']:
                if col in movies.columns:
                    movies[col] = movies[col].astype(str)
            return movies[movie_fields + ["match_count", "similarity"]].to_dict(orient="records")

        # Tính số thể loại khớp cho mỗi phim
        def count_matching_genres(movie_genres):
            return sum(1 for genre in preferred_genres if movie_genres.get(genre, 0) == 1)

        # Tạo DataFrame với số thể loại khớp
        match_counts = movies_genres.apply(count_matching_genres, axis=1)
        similarity_scores = cosine_similarity(user_profile.values.reshape(1, -1), movies_genres.values)[0]
        similarity_df = pd.DataFrame({
            "movieId": movies_genres.index,
            "match_count": match_counts,
            "similarity": similarity_scores
        })

        # Nhóm phim theo số thể loại khớp
        grouped_movies = []
        max_matches = min(len(preferred_genres), max(match_counts))
        used_movie_ids = set()

        for match_count in range(max_matches, -1, -1):
            group = similarity_df[similarity_df["match_count"] == match_count].copy()
            if not group.empty:
                # Sắp xếp trong nhóm theo similarity và popularity
                group = group.merge(movies_df[movie_fields + ["popularity"]], left_on="movieId", right_on="_id")
                
                # Kiểm tra cột trùng lặp sau merge
                duplicate_columns_after_merge = group.columns[group.columns.duplicated()]
                if not duplicate_columns_after_merge.empty:
                    print(f"Warning: Found duplicate columns after merge in recommend_movies: {duplicate_columns_after_merge}. Keeping the last one.", file=sys.stderr)
                    group = group.loc[:, ~group.columns.duplicated(keep='last')]

                group = group[~group["movieId"].isin(used_movie_ids)]
                if not group.empty:
                    group = group.sort_values(by=["match_count", "similarity", "popularity"], ascending=[False, False, False])
                    grouped_movies.append(group[movie_fields + ["match_count", "similarity"]])
                    used_movie_ids.update(group["movieId"].values)

        if not grouped_movies:
            # Nếu không có phim khớp, trả về tất cả phim còn lại, sắp xếp theo popularity
            remaining_movies = movies_df[~movies_df["_id"].isin(used_movie_ids)][movie_fields + ["popularity"]].copy()
            remaining_movies["match_count"] = 0
            remaining_movies["similarity"] = 0.0
            remaining_movies = remaining_movies.sort_values(by="popularity", ascending=False)
            # Chuyển đổi cột datetime thành chuỗi trước khi trả về
            for col in ['releaseDate']:
                if col in remaining_movies.columns:
                    remaining_movies[col] = remaining_movies[col].astype(str)
            return remaining_movies[movie_fields + ["match_count", "similarity"]].to_dict(orient="records")

        recommendations = pd.concat(grouped_movies, ignore_index=True)
        # Chuyển đổi cột datetime thành chuỗi trước khi trả về
        for col in ['releaseDate']:
            if col in recommendations.columns:
                recommendations[col] = recommendations[col].astype(str)
        return recommendations[movie_fields + ["match_count", "similarity"]].to_dict(orient="records")

    except Exception as e:
        print(f"Error in recommend_movies: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
        try:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            user_profiles = pd.read_pickle(os.path.join(data_dir, "user_profiles.pkl"))
            movies_genres = pd.read_pickle(os.path.join(data_dir, "movies_genres.pkl"))
            movies_df = pd.read_pickle(os.path.join(data_dir, "movies_df.pkl"))
            recommendations = recommend_movies(user_id, user_profiles, movies_genres, movies_df)
            print(json.dumps(recommendations, ensure_ascii=False))
            sys.exit(0)
        except Exception as e:
            print(f"Error loading pickle files or generating recommendations: {str(e)}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Training completed and data saved", file=sys.stderr)
        sys.exit(0)