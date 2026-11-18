# Trained models

Put the files exported by the Kaggle notebooks here (see `/kaggle/README.md`):

```
models/
├── speaking_traits.joblib        ← 01_speaking_pronunciation_fluency.ipynb, part A
├── speaking_ssl/                 ← 01_speaking_pronunciation_fluency.ipynb, part B (optional)
│   ├── model.onnx
│   └── config.json
└── essay_traits/                 ← 02_writing_traits_ellipse.ipynb
    ├── model.onnx
    ├── tokenizer.json
    └── config.json
```

Every model is optional. Restart the API after adding files; **Settings → Scoring engine** in the app shows what's loaded.
Large files (`*.onnx`) are git-ignored — keep them in Kaggle Datasets, GitHub Releases or object storage.
