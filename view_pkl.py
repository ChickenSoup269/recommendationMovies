import pandas as pd
import os

data_dir = "data"

user_profiles = pd.read_pickle(os.path.join(data_dir, "user_profiles.pkl"))
movies_genres = pd.read_pickle(os.path.join(data_dir, "movies_genres.pkl"))
movies_df = pd.read_pickle(os.path.join(data_dir, "movies_df.pkl"))

print("User Profiles:")
print(user_profiles)
print("\nMovies Genres:")
print(movies_genres)
print("\nMovies DataFrame:")
print(movies_df)