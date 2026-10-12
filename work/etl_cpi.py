# /// script
# requires-python = ">=3.10"
# dependencies = ["xlrd", "pandas"]
# ///
"""ETL：主計總處 cpispl.xls（消費者物價指數銜接表 + 年增率）-> work/cpi_clean.csv

用法：uv run work/etl_cpi.py [xls 路徑]
預設先找 data/cpispl.xls，找不到再找專案根目錄的 cpispl.xls。原始檔只讀不寫。
"""
import sys
from pathlib import Path

import pandas as pd
import xlrd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "work" / "cpi_clean.csv"


def find_source() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    for p in (ROOT / "data" / "cpispl.xls", ROOT / "cpispl.xls"):
        if p.exists():
            return p
    sys.exit("找不到 cpispl.xls")


def read_wide(sheet) -> dict:
    """把一張「民國年 x 1~12月」的表轉成 {(民國年, 月): 值}。空白格不輸出（不補值）。"""
    hdr = next(r for r in range(sheet.nrows) if str(sheet.cell_value(r, 0)).strip() == "民國年")
    months = {}
    for c in range(1, sheet.ncols):
        label = str(sheet.cell_value(hdr, c)).strip()
        if label.endswith("月") and label[:-1].isdigit():
            months[c] = int(label[:-1])  # 「累計平均」等非月份欄位會被略過
    data = {}
    for r in range(hdr + 1, sheet.nrows):
        y = sheet.cell_value(r, 0)
        if not isinstance(y, float):  # 備註列、空白列
            continue
        for c, m in months.items():
            v = sheet.cell_value(r, c)
            if isinstance(v, float):
                data[(int(y), m)] = v
            elif v != "":
                raise ValueError(f"非數字內容 r{r} c{c}: {v!r}")
    return data


def main():
    src = find_source()
    wb = xlrd.open_workbook(src)
    idx = read_wide(wb.sheet_by_name("CPI"))
    yoy = read_wide(wb.sheet_by_name("年增率"))

    rows = []
    for (y, m) in sorted(set(idx) | set(yoy)):
        rows.append({
            "roc_year": y,
            "year": y + 1911,
            "month": m,
            "period": f"{y + 1911}-{m:02d}",
            "cpi_index": idx.get((y, m)),
            "yoy_pct": yoy.get((y, m)),
        })
    df = pd.DataFrame(rows)
    df["cpi_index"] = df["cpi_index"].astype("Float64")
    df["yoy_pct"] = df["yoy_pct"].astype("Float64")

    # ---------- 驗證 ----------
    assert not df.duplicated(["year", "month"]).any(), "年月重複"
    assert df["cpi_index"].notna().all(), "cpi_index 有缺漏"
    # 年增率起算年份比指數晚一年，這些缺漏是預期的；其餘不應缺漏
    miss = df[df["yoy_pct"].isna()]
    print(f"來源：{src}")
    print(f"期間：{df.period.iloc[0]} ~ {df.period.iloc[-1]}，共 {len(df)} 筆")
    print(f"yoy 缺漏 {len(miss)} 筆，範圍 {miss.period.min()} ~ {miss.period.max()}")
    # 連續性：月份應無斷點
    full = pd.period_range(df.period.iloc[0], df.period.iloc[-1], freq="M").astype(str)
    assert list(full) == list(df.period), "月份不連續"

    # 交叉驗證：由指數自行推算年增率，與官方公布值比較
    s = df.set_index("period")["cpi_index"].astype(float)
    calc = (s / s.shift(12) - 1) * 100
    diff = (calc - df.set_index("period")["yoy_pct"].astype(float)).abs().dropna()
    print(f"自算年增率 vs 官方：最大差 {diff.max():.2f} 個百分點；差>0.1 的有 {(diff > 0.1).sum()} 筆")
    if (diff > 0.1).any():
        print(diff[diff > 0.1].round(2).to_string())

    OUT.parent.mkdir(exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"已輸出 {OUT}")


if __name__ == "__main__":
    main()
