# 🚀 Quick Start: Getting the App Running

Your app now **runs even if PostgreSQL is not available**. Here's how:

---

## 🎯 3-Step Quick Start

### 1. Install Dependencies (if not done)
```bash
pip install -r requirements.txt
```

### 2. Start the App
```bash
python app.py
```

### 3. Open in Browser
Visit: **http://localhost:5000**

---

## ✅ What You'll See

### Success (Without Database)
```
 * Running on http://127.0.0.1:5000
⚠️  Database not available: connection to server at "localhost"...
   App will run in offline mode (embeddings only)
```

✅ **This is NORMAL and FINE!** The app is running.

### Success (With Database)
```
 * Running on http://127.0.0.1:5000
✓ Connected to PostgreSQL
✓ Database tables initialized
```

✅ You have both database and app running.

---

## 🧪 Testing Without Database

All features work without PostgreSQL:

1. **Upload Image**
   - Go to: http://localhost:5000/upload
   - Enter Product ID and angle
   - Upload JPEG/PNG
   - ✅ Works offline

2. **Search Similar**
   - Go to: http://localhost:5000/search
   - Upload query image
   - ✅ Returns similar images

3. **Advanced Embeddings**
   - CLIP model loads automatically
   - Takes 2-5 min on first run
   - Then instant
   - ✅ All features work

---

## ⚙️ If You Want Database Support

See: [DATABASE_SETUP.md](DATABASE_SETUP.md)

Quick steps:
1. Have PostgreSQL running
2. Update `.env` with correct password
3. Restart app

---

## ❌ Troubleshooting

### Issue: App crashes immediately
**Solution:** Check the error message. If it says "Database not available", that's OK - the app should still start.

### Issue: Port 5000 already in use
```python
# Edit app.py, bottom:
if __name__ == '__main__':
    app.run(debug=True, port=5001)  # Change port
```

### Issue: "ModuleNotFoundError"
```bash
# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: CLIP model download fails
- Check internet connection
- Try again (downloads ~500MB)
- Took 2-5 minutes on first run

---

## 🎉 You're Ready!

Just run:
```bash
python app.py
```

Then visit: http://localhost:5000

All advanced CLIP embedding features work out of the box! 🚀

---

**Next:** See [DATABASE_SETUP.md](DATABASE_SETUP.md) if you want to set up PostgreSQL
