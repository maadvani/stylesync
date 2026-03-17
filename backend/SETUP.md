# Backend setup (local / $0 tier)

## 1. Cloudinary (image storage)

- Go to [cloudinary.com](https://cloudinary.com) and sign up (free).
- In the Dashboard you’ll see **Cloud name**, **API Key**, and **API Secret**.
- Add them to your `backend/.env`:

```env
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

Use no spaces around `=` (e.g. `CLOUDINARY_CLOUD_NAME=stylesync` not `= stylesync`). No credit card needed; free tier is enough for hundreds of wardrobe images.

---

## 2. Hugging Face token (image caption)

- Go to [huggingface.co](https://huggingface.co), sign up, then **Settings → Access Tokens**.
- Create a token (read is enough for Inference API).
- Add to `backend/.env`:

```env
HF_TOKEN=hf_xxxxxxxxxxxx
```

The backend uses the **Inference API** (serverless). No GPU or local model needed.

---

## 3. Supabase tables

- Open your Supabase project → **SQL Editor**.
- Run **`supabase_wardrobe_items.sql`** once to create the `wardrobe_items` table.
- Run **`supabase_user_profiles.sql`** once to create the `user_profiles` table (for color quiz result).

You already have `SUPABASE_URL` and `SUPABASE_KEY` in `.env`.

Your `.env` already has placeholders for `CLOUDINARY_*`; add `HF_TOKEN` as well (see step 2).

---

## 4. Run the API

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

- Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Frontend should call `http://127.0.0.1:8000/api/wardrobe/upload` (POST) and `http://127.0.0.1:8000/api/wardrobe` (GET).
