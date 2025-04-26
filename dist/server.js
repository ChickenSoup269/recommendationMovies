"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const recommendationRoutes_1 = __importDefault(require("./recommendationRoutes"));
const dotenv_1 = __importDefault(require("dotenv"));
dotenv_1.default.config();
const app = (0, express_1.default)();
app.use((0, cors_1.default)({
    origin: process.env.CORS_ORIGIN || "http://localhost:3000",
    methods: ["GET", "POST"],
}));
app.use(express_1.default.json());
app.use("/api/movies", recommendationRoutes_1.default);
app.use((err, req, res, next) => {
    console.error("Unexpected error:", err);
    res.status(500).json({ error: "Internal server error" });
});
const PORT = parseInt(process.env.PORT || "5000", 10);
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
