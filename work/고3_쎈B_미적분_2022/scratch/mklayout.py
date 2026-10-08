import json
m = json.load(open(r"work/고3_쎈B_미적분_2022/scratch/manual.json", encoding="utf-8"))
lay = {
  "source": "ocr",
  "pages": [[7, 142]],
  "skip_pages": [20, 35, 36, 47, 48, 62, 63, 64, 76, 89, 90, 103, 104, 116, 117, 118, 130],
  "label_regex": "^(ZZZZ)$",
  "rescue": False,
  "groups": False,
  "drop_outliers": False,
  "body": [46, 790],
  "columns": [{"x": [44, 309], "label_x": [50, 80]}, {"x": [318, 580], "label_x": [320, 345]}],
  "top_pad": 10,
  "bot_pad": 9,
  "gap_stop": 45,
}
s = json.dumps(lay, ensure_ascii=False, indent=2)
rows = ",\n    ".join(json.dumps(x) for x in m)
s = s[:-2] + ',\n  "manual_labels": [\n    ' + rows + "\n  ]\n}\n"
open(r"work/고3_쎈B_미적분_2022/layout.json", "w", encoding="utf-8").write(s)
