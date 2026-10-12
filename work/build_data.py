# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas"]
# ///
"""work/cpi_clean.csv -> docs/data.js（網頁用，以 <script src="data.js"> 載入，不需 fetch）

資料結構（window.CPI_DATA）：
  meta   : 來源、基期、期間、單位、限制說明
  years  : 西元年份升冪陣列
  index  : {年: [1~12 月 CPI 指數，缺值為 null]}
  yoy    : {年: [1~12 月 年增率(%)，缺值為 null]}
只含「總指數」；來源檔沒有商品類別，所以不輸出 category。
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "work" / "cpi_clean.csv"
OUT = ROOT / "docs" / "data.js"


def main():
    if not SRC.exists():
        sys.exit(f"找不到 {SRC}，請先執行 work/etl_cpi.py")
    df = pd.read_csv(SRC, encoding="utf-8-sig")

    need = {"year", "month", "cpi_index", "yoy_pct"}
    if not need <= set(df.columns):
        sys.exit(f"CSV 欄位不足，缺少 {need - set(df.columns)}")
    df = df[["year", "month", "cpi_index", "yoy_pct"]]

    # 資料品質檢查
    assert not df.duplicated(["year", "month"]).any(), "年月重複"
    assert df["month"].between(1, 12).all(), "月份超出 1~12"
    assert df["cpi_index"].notna().all(), "cpi_index 有缺值"
    assert pd.to_numeric(df["cpi_index"], errors="coerce").notna().all(), "cpi_index 非數字"

    def cell(v):
        return None if pd.isna(v) else round(float(v), 2)

    years = sorted(int(y) for y in df["year"].unique())
    index = {str(y): [None] * 12 for y in years}
    yoy = {str(y): [None] * 12 for y in years}
    for r in df.itertuples(index=False):
        index[str(r.year)][int(r.month) - 1] = cell(r.cpi_index)
        yoy[str(r.year)][int(r.month) - 1] = cell(r.yoy_pct)

    last = df.sort_values(["year", "month"]).iloc[-1]
    data = {
        "meta": {
            "source": "行政院主計總處 消費者物價指數銜接表（cpispl.xls）",
            "base": "民國110年(2021)=100",
            "unit": {"index": "指數點", "yoy": "%"},
            "first": f"{int(df.year.min())}-01",
            "last": f"{int(last.year)}-{int(last.month):02d}",
            "rocOffset": 1911,
            "records": int(len(df)),
            "note": "僅有總指數，無商品類別；民國59年(含)以前依台灣省政府指數銜接；"
                    "最近3個月資料可能修正；年增率自民國49年起（1959年為 null）。",
        },
        "years": years,
        "index": index,
        "yoy": yoy,
    }

    OUT.parent.mkdir(exist_ok=True)
    js = "window.CPI_DATA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    OUT.write_text(js, encoding="utf-8")
    print(f"已輸出 {OUT}（{OUT.stat().st_size / 1024:.1f} KB），{len(df)} 筆，{len(years)} 個年份")


if __name__ == "__main__":
    main()
