"use strict"
var __awaiter =
  (this && this.__awaiter) ||
  function (thisArg, _arguments, P, generator) {
    function adopt(value) {
      return value instanceof P
        ? value
        : new P(function (resolve) {
            resolve(value)
          })
    }
    return new (P || (P = Promise))(function (resolve, reject) {
      function fulfilled(value) {
        try {
          step(generator.next(value))
        } catch (e) {
          reject(e)
        }
      }
      function rejected(value) {
        try {
          step(generator["throw"](value))
        } catch (e) {
          reject(e)
        }
      }
      function step(result) {
        result.done
          ? resolve(result.value)
          : adopt(result.value).then(fulfilled, rejected)
      }
      step((generator = generator.apply(thisArg, _arguments || [])).next())
    })
  }
var __importDefault =
  (this && this.__importDefault) ||
  function (mod) {
    return mod && mod.__esModule ? mod : { default: mod }
  }
Object.defineProperty(exports, "__esModule", { value: true })
const express_1 = __importDefault(require("express"))
const child_process_1 = require("child_process")
const path_1 = __importDefault(require("path"))
const router = express_1.default.Router()
router.get("/recommendations", (req, res) =>
  __awaiter(void 0, void 0, void 0, function* () {
    const userId = req.query.userId
    if (!userId) {
      return res.status(400).json({ error: "Valid userId is required" })
    }
    try {
      const pythonScriptPath = path_1.default.join(
        __dirname,
        "..",
        "models",
        "recommend.py"
      )
      console.log("Python script path:", pythonScriptPath)
      // Gọi script Python
      const pythonProcess = (0, child_process_1.spawn)(
        "python",
        [pythonScriptPath, userId],
        {
          timeout: 30000,
          env: Object.assign(Object.assign({}, process.env), {
            PYTHONIOENCODING: "utf-8",
          }),
        }
      )
      let recommendations = ""
      let errorOutput = ""
      pythonProcess.stdout.on("data", (data) => {
        recommendations += data.toString()
        console.log("Python stdout:", data.toString())
      })
      pythonProcess.stderr.on("data", (data) => {
        errorOutput += data.toString()
        console.log("Python stderr:", data.toString())
      })
      pythonProcess.on("close", (code) => {
        if (res.headersSent) return
        console.log("Python process exited with code:", code)
        if (code === 0) {
          try {
            const parsedRecommendations = JSON.parse(recommendations.trim())
            res.status(200).json({
              status: "OK",
              message: "Lấy gợi ý phim thành công",
              data: parsedRecommendations,
            })
          } catch (err) {
            console.error("Error parsing recommendations:", err)
            res.status(500).json({
              error: "Invalid recommendation data format",
              details: recommendations || "No output received",
            })
          }
        } else {
          console.error("Python script error:", errorOutput)
          res.status(500).json({
            error: "Error generating recommendations",
            details: errorOutput || `Unknown error (exit code: ${code})`,
          })
        }
      })
      pythonProcess.on("error", (err) => {
        if (res.headersSent) return
        console.error("Process error:", err)
        res.status(500).json({
          error: "Failed to execute recommendation script",
          details: err.message,
        })
      })
    } catch (error) {
      if (res.headersSent) return
      console.error("Server error:", error)
      res.status(500).json({
        error: "Internal server error",
        details: error.message,
      })
    }
  })
)
exports.default = router
