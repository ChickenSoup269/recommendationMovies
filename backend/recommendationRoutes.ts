  import express from "express";
  import { spawn } from "child_process";
  import path from "path";

  const router = express.Router();

  router.get("/recommendations", async (req: any, res: any) => {
    const userId = req.query.userId as string | undefined;

    if (!userId) {
      return res.status(400).json({ error: "Valid userId is required" });
    }

    try {
      const pythonScriptPath = path.join(
        __dirname,
        "..",
        "models",
        "recommend.py"
      );
    console.log('Python script path:', pythonScriptPath); // Log path
      // Gọi script Python
      const pythonProcess = spawn("python", [pythonScriptPath, userId], {
        timeout: 30000,
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      });

      let recommendations = "";
      let errorOutput = "";

      pythonProcess.stdout.on("data", (data: Buffer) => {
        recommendations += data.toString();
        console.log("Python stdout:", data.toString());
      });

      pythonProcess.stderr.on("data", (data: Buffer) => {
        errorOutput += data.toString();
        console.log("Python stderr:", data.toString());
      });

      pythonProcess.on('error', (err) => {
      console.log('Spawn error:', err.message); 
      res.status(500).json({
        error: 'Failed to execute Python script',
        details: err.message,
      });
    });

    pythonProcess.on('close', (code: number | null) => {
      console.log('Python process exited with code:', code);
      if (code === 0) {
        try {
          const parsedRecommendations = JSON.parse(recommendations.trim());
          res.status(200).json({
            status: 'OK',
            message: 'Lấy gợi ý phim thành công',
            data: parsedRecommendations,
          });
        } catch (err) {
          console.log('JSON parse error:', err);
          res.status(500).json({
            error: 'Invalid recommendation data format',
            details: recommendations || 'No output received',
          });
        }
      } else {
        res.status(500).json({
          error: 'Error generating recommendations',
          details: errorOutput || `Unknown error (exit code: ${code})`,
        });
      }
    });
    } catch (error) {
      if (res.headersSent) return;
      console.error("Server error:", error);
      res.status(500).json({
        error: "Internal server error",
        details: (error as Error).message,
      });
    }
  });

  export default router;
