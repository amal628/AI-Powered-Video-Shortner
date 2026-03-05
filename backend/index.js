// backend/index.js

const express = require('express');
const path = require('path');
const cors = require('cors');
const multer = require('multer');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 8000;

// -------------------- MIDDLEWARE --------------------
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Enable CORS only in development (optional)
if (process.env.NODE_ENV !== 'production') {
  app.use(cors());
}

// -------------------- FILE UPLOAD SETUP --------------------
const uploadDir = path.join(__dirname, 'uploads');

// Ensure uploads folder exists
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadDir),
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1e9);
    const ext = path.extname(file.originalname);
    cb(null, `${file.fieldname}-${uniqueSuffix}${ext}`);
  },
});
const upload = multer({ storage });

// -------------------- API ROUTES --------------------

// Test API
app.get('/api/hello', (req, res) => {
  res.json({ message: 'Hello from backend!' });
});

// File upload API
app.post('/api/upload', upload.single('file'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'No file uploaded' });
  }
  res.json({ fileId: req.file.filename, originalName: req.file.originalname });
});

// -------------------- SERVE FRONTEND --------------------
const frontendPath = path.join(__dirname, '../frontend/dist');
app.use(express.static(frontendPath));

// -------------------- START SERVER --------------------
app.listen(PORT, () => {
  console.log(`Backend server running at http://localhost:${PORT}`);
});