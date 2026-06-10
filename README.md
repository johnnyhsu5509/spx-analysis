# SPX Analysis

SPX 日線技術分析 + 回測系統。儀表板：https://johnnyhsu5509.github.io/spx-analysis/

## 結構

```
docs/                  GitHub Pages（儀表板 HTML + last_analysis.json）
skills/spx-analysis/   Claude Code SKILL.md
scripts/               Python 數據腳本（yfinance）
```

## 新電腦安裝（一次性，約 3 分鐘）

1. **Clone 本 repo**（放哪都可以）：
   ```
   git clone https://github.com/johnnyhsu5509/spx-analysis.git
   ```

2. **安裝 Python 套件**（需先裝 Python 3.10+）：
   ```
   pip install -r spx-analysis/scripts/requirements.txt
   ```

3. **安裝 SKILL 給 Claude Code**：把 `skills/spx-analysis/` 複製到 `C:\Users\<你>\.claude\skills\`：
   ```
   Copy-Item -Recurse spx-analysis\skills\spx-analysis C:\Users\$env:USERNAME\.claude\skills\
   ```

4. 開 Claude Code，在 repo 資料夾內說「分析今日SPX」即可。

## 日常指令

| 時間（台灣） | 指令 | 作用 |
|---|---|---|
| 白天 | 分析今日SPX | 回測+分析+建議，推 GitHub Pages |
| 21:20 | 期貨確認 | ES/NQ/VIX 快速確認（30秒）|
| 22:00 後 | 開盤確認 | 前30分鐘K棒方向+量能（5分鐘）|

## 更新同步

任何電腦上改了 SKILL 或腳本 → `git push`；其它電腦 `git pull` 即同步。
