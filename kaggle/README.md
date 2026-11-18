# Training ParPTE's models on Kaggle

Both notebooks run on Kaggle's free GPUs (30 h/week), so training costs you nothing locally.

## Before you start

1. Create a Kaggle account and **verify your phone number**. That unlocks GPUs and internet access in notebooks.
2. If the GitHub repo is private: create a fine-grained GitHub token with read-only access to `ParPTE`, then add it in the notebook under **Add-ons → Secrets** as `GITHUB_TOKEN`. The speaking notebook clones the repo so it uses the app's own feature extractor.

## 1 · Speaking: `01_speaking_pronunciation_fluency.ipynb`

* Kaggle → **Create → New Notebook → File → Import Notebook**, and upload this file.
* Settings: **Accelerator GPU T4 x1**, **Internet on**. Then **Run all**.
* Part A takes about 30 minutes. Set `RUN_PART_B = True` to also fine-tune wav2vec2 (about 1.5 h extra).
* Download `parpte_speaking_models.zip` from **Output** and unzip it into `backend/models/`.

The model learns from speechocean762's expert ratings (pronunciation accuracy, fluency, prosody on 0–10), using exactly the features the server computes. That data is mostly Mandarin L1 speakers reading short sentences, so the model is strongest on Read Aloud and Repeat Sentence. The rubric scorer still governs the longer tasks.

## 2 · Writing: `02_writing_traits_ellipse.ipynb`

* Join the [Feedback Prize – English Language Learning](https://www.kaggle.com/competitions/feedback-prize-english-language-learning) competition, accept its rules, and add it as input to the notebook.
* Settings: **GPU T4 or P100**, **Internet on**, then **Run all** (about 2 h for `deberta-v3-base`, about 40 min for `-small`).
* Download `parpte_writing_models.zip` and unzip it into `backend/models/` (it contains `essay_traits/`).
* Read the licence note in the notebook before using this model for paying users.

## Afterwards

Restart the API. **Settings → Scoring engine** lists the trained models that loaded. Keep the large `.onnx` files out of git (they're already ignored). Store them as a Kaggle Dataset or a GitHub Release, and mount them in production (`docker-compose.yml` mounts `backend/models`).
