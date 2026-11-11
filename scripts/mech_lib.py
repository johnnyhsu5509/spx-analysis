"""排程瘦身腳本共用：帳本讀寫、交易日、判定 session、影子單成交、深度合併、數值比對。"""
import datetime
import html
import json
import math
import re
from decimal import ROUND_HALF_UP, Decimal


def ld(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def sv(p, o):
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(o, ensure_ascii=False, indent=1))


def next_bday(d):
    t = datetime.date.fromisoformat(d) + datetime.timedelta(days=1)
    while t.weekday() >= 5:
        t += datetime.timedelta(days=1)
    return t.isoformat()


def md(d):
    t = datetime.date.fromisoformat(d[:10])
    return f'{t.month}/{t.day}'


def eval_session(td, target):
    """待判定預測的目標 session：通常就是 today_data 當天；中間漏跑（gap day）時從 recent_5 取，並回傳 gap day 清單。"""
    day = td['trade_date']
    if target == day:
        return {'o': td['open'], 'h': td['high'], 'l': td['low'], 'c': td['close'], 'pc': td['prev_close'], 'chg': td.get('change_pct')}, []
    rows = td.get('recent_5') or []
    idx = [i for i, r in enumerate(rows) if r['date'] == target]
    if target > day or not idx or idx[0] == 0 or rows[-1]['date'] != day:
        raise SystemExit(f'待判定預測的目標日 {target} 不在 today_data（{day}）的 recent_5 裡，請人工記帳')
    i = idx[0]
    r, pc = rows[i], rows[i - 1]['close']
    return {'o': r['open'], 'h': r['high'], 'l': r['low'], 'c': r['close'], 'pc': pc, 'chg': None}, [x['date'] for x in rows[i + 1:]]


def shadow_fill(side, lim, a, s, o, h, lo, c):
    """影子單：成交價＝min／max(掛單價, 開盤價)，停損優先，否則收盤平倉。未成交回傳 None。"""
    if side == 'long':
        if lo > lim:
            return None
        fill = min(lim, o)
        stop = round(fill - s * a, 2)
        hit = lo <= stop
        ex = stop if hit else c
        pts = round(ex - fill, 2)
    else:
        if h < lim:
            return None
        fill = max(lim, o)
        stop = round(fill + s * a, 2)
        hit = h >= stop
        ex = stop if hit else c
        pts = round(fill - ex, 2)
    return {'fill': fill, 'gap': fill != lim, 'stop': stop, 'stop_hit': hit, 'exit': ex, 'pnl_pts': pts, 'pnl_A': round(pts / a, 3)}


def hu(x, nd=1):
    """一般四捨五入（浮點格式遇 .5 不一定進位）。"""
    return float(Decimal(str(x)).quantize(Decimal(1).scaleb(-nd), ROUND_HALF_UP))


def mean_hu(xs, nd=3):
    """精確十進位平均＋一般四捨五入。浮點平均剛好落在半位時，round() 看的是二進位表示，會進錯位（2026-11-04：-0.0095 得 -0.009，應為 -0.010）。"""
    d = [Decimal(str(x)) for x in xs]
    return float((sum(d) / len(d)).quantize(Decimal(1).scaleb(-nd), ROUND_HALF_UP))


def log_err(actual, ref):
    return round(abs(math.log(actual / ref)), 4)


def merge(dst, src, shallow, deep=()):
    """src 的頂層鍵整段取代；shallow 列出的鍵只覆蓋給到的子鍵，deep 列出的鍵再往下一層。"""
    for k, v in src.items():
        if k in shallow and isinstance(v, dict) and isinstance(dst.get(k), dict):
            for kk, vv in v.items():
                if k in deep and isinstance(vv, dict) and isinstance(dst[k].get(kk), dict):
                    dst[k][kk].update(vv)
                else:
                    dst[k][kk] = vv
        else:
            dst[k] = v
    return dst


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def walk_diffs(a, b, path=''):
    """逐欄比對 a（腳本）與 b（實跑）。回傳 (kind, path, a, b)：kind ∈ value／only_mech／only_actual／length。"""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(b) + [k for k in a if k not in b]:
            p = f'{path}.{k}' if path else k
            if k not in a:
                out.append(('only_actual', p, None, b[k]))
            elif k not in b:
                out.append(('only_mech', p, a[k], None))
            else:
                out += walk_diffs(a[k], b[k], p)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(('length', path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            out += walk_diffs(x, y, f'{path}[{i}]')
    elif a != b or isinstance(a, bool) != isinstance(b, bool):
        out.append(('value', path, a, b))
    return out


def numeric(d, tol=0.0):
    """只留數值差異：任一邊是數字／布林／null 對數字，或筆數不同；|差| ≤ tol 視為相同。"""
    kind, _, a, b = d
    if kind == 'length':
        return True
    if kind in ('only_mech', 'only_actual'):
        v = a if kind == 'only_mech' else b
        return is_num(v) or isinstance(v, bool)
    if isinstance(a, str) or isinstance(b, str) or isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        return False
    if is_num(a) and is_num(b):
        return abs(a - b) > tol
    return True


# ---- Phase 3 修正（2026-11-04）：部位水位、振幅命中率、頂端摘要行 ----

AMP_HIT_DEF = '實際振幅 (高−低)/前收×100 落在預報當時發布的 50% 區間 [band_lo, band_hi]（含端點）'
P3_SUM = ('<!--phase3:summary-->', '<!--/phase3:summary-->')
P3_POS = ('<!--phase3:position-->', '<!--/phase3:position-->')
BANNER_STYLE = ('margin:0 0 16px;padding:12px 16px;border:1px solid #00e5ff;border-left:5px solid #00e5ff;'
                'border-radius:8px;background:#0b1f26;color:#e0e0e0;line-height:1.6')


def seed_position(track):
    """track_record 的 position_gate.events 最後一筆 → 前一日 position_level 的最小種子（state、since）；沒有就回傳 None。"""
    ev = (track.get('position_gate') or {}).get('events') or []
    return {'state': ev[-1]['to'], 'since': ev[-1]['date']} if ev else None


def position_level(old, close, ma200, day):
    """部位水位（rule59／prc-014）：NDX 與 SPX 共用同一段判定。close > ma200 → 正常；否則 → 半倉。
    old＝前一日的 position_level（只用 state、since）；None＝首次建立（起算日未登記，since 為 None）。
    水位切換或處於半倉時停下，要求人工處理（含 position_gate.events）。"""
    pct = round((close / ma200 - 1) * 100, 2)
    dist = round((1 - ma200 / close) * 100, 2)
    state = '正常' if close > ma200 else '半倉'
    if old is not None and state != old['state']:
        raise SystemExit(f"部位水位切換 {old['state']} → {state}：rule59 事件，請人工處理（含 position_gate.events）")
    if state != '正常':
        raise SystemExit('部位水位為半倉：只驗證過正常狀態的文字模板，請人工處理')
    return {'state': state, 'close': close, 'ma200': ma200, 'pct': pct, 'since': old['since'] if old else None, 'switched_today': False,
            'data_missing': False, 'basis_date': day, 'dist_to_switch_pct': dist, 'note': f'收盤需再跌約 {dist:.1f}% 才轉半倉'}


def amp_hit_rate(entries):
    """振幅預報命中率：逐筆用 band_lo／band_hi 與 actual_range_pct 重判（不抄 in_band 旗標），NDX 與 SPX 各自傳入自己的 amp_track.entries。"""
    rows = [e for e in entries if e.get('actual_range_pct') is not None]
    n = len(rows)
    pos = ['in' if e['band_lo'] <= e['actual_range_pct'] <= e['band_hi'] else 'low' if e['actual_range_pct'] < e['band_lo'] else 'high' for e in rows]
    days = sorted(e['eval_date'] for e in rows)
    return {'definition': AMP_HIT_DEF, 'n': n, 'date_from': days[0] if n else None, 'date_to': days[-1] if n else None,
            'hits': pos.count('in'), 'rate_pct': round(pos.count('in') / n * 100, 1) if n else None,
            'below_band': pos.count('low'), 'above_band': pos.count('high'),
            'source': 'amp_track.entries（逐筆以 band_lo／band_hi 與 actual_range_pct 重判）',
            'note': f'n={n}，未達 60 筆，無統計意義' if n < 60 else f'n={n}，已達 60 筆，可判定'}


def _levels(xs, k=2):
    return '／'.join(f'{x:,.0f}' for x in (xs or [])[:k]) or '—'


def event_text(ev):
    """event_day＝{is_event_day: true|false|null, note}；null 代表敘事沒有標註（不猜），顯示「未標註」。"""
    if not ev or ev.get('is_event_day') is None:
        return '未標註'
    return ('是' if ev['is_event_day'] else '否') + (f"（{ev['note']}）" if ev.get('note') else '')


def summary_line(sym, la, pos):
    """頂端一行摘要：資料日、方向、A、關鍵價位／MA200、預報日是否事件日。la 須已含 amplitude、predictions、event_day、direction。"""
    am, pr = la['amplitude'], la.get('predictions') or {}
    # SPX 的水位只描述 SPX 自己；科技／NDX／QQQ／半導體這一籃的倉位一律跟 NDX（見 holding_action），避免兩個「水位」被讀成矛盾
    lvl = f"SPX 自身水位{pos['state']}；科技籃倉位跟 NDX" if sym == 'SPX' else f"水位{pos['state']}"
    return (f"{sym}｜資料日 {la['data_basis'][:10]}（收 {la['close']:,.2f}）｜方向 {la['direction']['prob']}（中性・無 edge）｜"
            f"A {hu(am['A_pct'], 2):.2f}%（約 ±{am['A_pts']:.0f} 點；50% 區間 {hu(am['band_lo'], 2):.2f}–{hu(am['band_hi'], 2):.2f}%）｜"
            f"MA200 {pos['ma200']:,.2f}（收盤 {pos['pct']:+.2f}%・{lvl}）｜"
            f"關鍵位 支撐 {_levels(pr.get('key_support'))} 壓力 {_levels(pr.get('key_resistance'))}｜"
            f"預報日 {la['trade_date']} 事件日：{event_text(la.get('event_day'))}")


def banner_html(la):
    """頁面頂端區塊：摘要行＋振幅命中率。含標記，可重複注入（取代舊區塊）。"""
    h = la['amp_hit_rate']
    rate = f"{h['hits']}/{h['n']} ＝ {h['rate_pct']}%（{h['date_from']}～{h['date_to']}）" if h['n'] else '尚無樣本'
    sub = f"振幅預報命中率（A 的 50% 區間）：{rate}；{h['note']}"
    ha = la.get('holding_action')
    top = ''
    if ha:
        top = (f'<div style="font-size:17px;font-weight:700;color:#00e5ff;margin-bottom:6px">{html.escape(ha["text"], quote=False)}</div>\n'
               f'<div style="font-size:13px;margin-bottom:6px">{html.escape(ha["new_long"], quote=False)}</div>\n')
        if ha.get('semis_ref'):
            top += f'<div style="font-size:12px;color:#9e9e9e;margin-bottom:8px">{html.escape(ha["semis_ref"], quote=False)}</div>\n'
    return (f'{P3_SUM[0]}\n<div class="phase3-summary" style="{BANNER_STYLE}">\n{top}'
            f'<div style="font-size:15px;font-weight:700">{html.escape(la["summary_line"], quote=False)}</div>\n'
            f'<div style="font-size:12px;color:#9e9e9e;margin-top:4px">{html.escape(sub, quote=False)}</div>\n</div>\n{P3_SUM[1]}')


def position_html(sym, pos):
    """SPX 報告最後一區（NDX 報告自己的版本在 render_ndx_html.py）；文字與 NDX 同一模板。"""
    reach = (f"收盤需再跌 {pos['dist_to_switch_pct']:.1f}% 才轉為半倉" if pos['state'] == '正常'
             else f"收盤需再漲 {pos.get('rise_to_reclaim_pct', round((pos['ma200'] / pos['close'] - 1) * 100, 2)):.1f}% 站回 MA200 才恢復正常")
    return (f'{P3_POS[0]}\n<h2>部位水位（部位層，不是分析）</h2>\n<div class="note">\n<ul>\n'
            f"<li>訊號：{sym} 收盤 {pos['close']:,.2f} vs MA200 {pos['ma200']:,.2f}（{pos['pct']:+.1f}%）→ 在 MA200 {'之上' if pos['pct'] > 0 else '之下'}</li>\n"
            f"<li>{sym} 自身水位：<b>{pos['state']}</b>（只描述 {sym}；科技／NDX／QQQ／半導體這一籃的倉位一律跟 NDX 閘門，見頁首第一句）</li>\n"
            f"<li>狀態：自 {pos['since'] or '（起算日未登記）'} 起維持；今日{'已' if pos['switched_today'] else '未'}切換</li>\n"
            f"<li>距切換線：{reach}</li>\n"
            '<li>依據：沿用 NDX 的 rule59／prc-014 判定式（收盤 &gt; MA200 → 正常，否則半倉）；prc-014 的樣本外驗證集含 SPX 1928–89，SPX 現行期間未另行登記。本段不改變上方的振幅與方向輸出。</li>\n'
            f'</ul>\n</div>\n{P3_POS[1]}')


def _swap(page, marks, block):
    pat = re.compile(re.escape(marks[0]) + '.*?' + re.escape(marks[1]), re.S)
    return pat.sub(lambda m: block, page, count=1) if pat.search(page) else None


def inject_banner(page, la):
    """把摘要區塊放在頁面最上方（<div class="wrap"> 之後，沒有就接在 <body> 之後）；已有標記就原地取代。"""
    block = banner_html(la)
    done = _swap(page, P3_SUM, block)
    if done is not None:
        return done
    for anchor in ('<div class="wrap">', '<body>'):
        i = page.find(anchor)
        if i >= 0:
            i += len(anchor)
            return page[:i] + '\n' + block + '\n' + page[i:]
    raise SystemExit('HTML 找不到 <div class="wrap"> 或 <body>，無法放摘要行')


def inject_position(page, block):
    """把部位水位區塊放在最後一個 <footer 之前；已有標記就原地取代。"""
    done = _swap(page, P3_POS, block)
    if done is not None:
        return done
    i = page.rfind('<footer')
    if i < 0:
        raise SystemExit('HTML 找不到 <footer>，無法放部位水位')
    return page[:i] + block + '\n\n' + page[i:]


# ---- 方案 G（2026-11-10）：報告第一句＝對現有持股的動作（維持／加碼／減碼），分母是科技／NDX／QQQ／半導體這一籃 ----

BASKET = '科技／NDX／QQQ／半導體相關持股'
NEW_LONG = '新增多單：不新增（本系統無方向 edge、預設不掛實單，rule57）。這一行只管新開倉，與上一句「現有持股」的動作是兩件事。'
EXIT_ALL = '出清不在現行規則內，另案討論'


def position_state(old, close, ma200, day):
    """部位水位（prc-014）的不中斷版：判定式與 position_level 相同（close > ma200 → 正常，否則半倉）；
    切換或處於半倉時不停下，改回報 switched_today。old＝前一日 position_level（只用 state、since）。"""
    pct = round((close / ma200 - 1) * 100, 2)
    dist = round((1 - ma200 / close) * 100, 2)
    rise = round((ma200 / close - 1) * 100, 2)
    state = '正常' if close > ma200 else '半倉'
    sw = old is not None and state != old['state']
    note = f'收盤需再跌約 {dist:.1f}% 才轉半倉' if state == '正常' else f'收盤需再漲約 {rise:.1f}% 站回 MA200 才恢復正常'
    if sw:
        note = ('今日切換 半倉 → 正常；' if state == '正常' else '今日切換 正常 → 半倉；') + note
    return {'state': state, 'close': close, 'ma200': ma200, 'pct': pct, 'since': day if sw else (old['since'] if old else None),
            'switched_today': sw, 'data_missing': False, 'basis_date': day, 'dist_to_switch_pct': dist,
            'rise_to_reclaim_pct': rise, 'note': note}


def holding_action(g, exec_day, data_note=''):
    """第一句：對現有持股的動作（只有 維持／加碼／減碼）。g＝NDX 閘門（position_state 輸出或 ndx_last_analysis 的 position_level）。"""
    ex = f'於 {md(exec_day)} 美股收盤執行'
    sig = f"NDX 收盤 {g['close']:,.2f}、MA200 {g['ma200']:,.2f}（{g['pct']:+.2f}%）"
    rise = g.get('rise_to_reclaim_pct', round((g['ma200'] / g['close'] - 1) * 100, 2))
    if g['state'] == '正常' and not g['switched_today']:
        act, tgt = '維持', 100
        body = f"維持 100%（滿倉）。{sig}；距切換線 {g['dist_to_switch_pct']:.1f}%，收盤跌破 MA200 才減到 50%（prc-014）。"
    elif g['state'] == '正常':
        act, tgt = '加碼', 100
        body = f"加碼到 100%（由 50% 加回滿倉）。{sig}，收盤站回 MA200；{ex}。"
    elif g['switched_today']:
        act, tgt = '減碼', 50
        body = f"減碼到 50%（半倉）。{sig}，收盤跌破 MA200；{ex}。{EXIT_ALL}。"
    else:
        act, tgt = '維持', 50
        body = f"維持 50%（半倉）。{sig}；收盤需再漲 {rise:.1f}% 站回 MA200 才加回 100%。{EXIT_ALL}。"
    text = f'對現有{BASKET}（以這一籃為 100%，不是帳戶總曝險）：{body}' + (f' {data_note}' if data_note else '')
    return {'basket': BASKET, 'denominator': '這一籃持股＝100%，不是帳戶總曝險', 'action': act, 'target_pct': tgt, 'text': text,
            'new_long': NEW_LONG, 'gate': 'NDX 收盤 vs MA200（prc-014，未改動）', 'exit_all': EXIT_ALL}


def ndx_gate(old, day, tds):
    """這一籃一律看 NDX 閘門（prc-014 是 NDX 規則；持科技／半導體的人看 SPX 水位會被誤導，rule15）。
    old＝ndx_last_analysis 的 position_level；tds＝候選的 NDX today_data（依序）。回傳 (閘門, 資料落後註記)。"""
    if old and old.get('basis_date') == day:
        return old, ''
    for t in tds:
        if old and t and t.get('symbol') == 'NDX' and t.get('trade_date') == day:
            return position_state(old, t['close'], t['ma200'], day), ''
    if old:
        return dict(old, switched_today=False), (f"⚠NDX 閘門資料日為 {old.get('basis_date')}（尚無 {day} 的 NDX 收盤），"
                                                 '沿用前一日水位，NDX 報告出來後以其為準。')
    raise SystemExit('找不到 NDX 閘門（ndx_last_analysis.json 沒有 position_level）：「現有持股動作」需要它')


def add_switch_event(tr, pl, name):
    """切換日在 track_record 的 position_gate.events 補一筆（同一訊號日不重複寫）；有寫回傳 True。"""
    ev = tr.setdefault('position_gate', {}).setdefault('events', [])
    if not pl['switched_today'] or any(e.get('date') == pl['basis_date'] for e in ev):
        return False
    ev.append({'date': pl['basis_date'], 'from': '半倉' if pl['state'] == '正常' else '正常', 'to': pl['state'], 'close': pl['close'],
               'ma200': pl['ma200'], 'note': f"{name} 收 {pl['close']:,.2f} 與 MA200 {pl['ma200']:,.2f}（{pl['pct']:+.2f}%）；t+1 美股收盤執行"})
    return True


def semis_for(td, alt_tds=()):
    """半導體日線：先用自己 today_data 的 semis_daily；沒有（舊版 fetch 產的檔、或 data/ 快照）就借同一資料日的另一份 today_data，
    並以自己指數的漲跌重算 vs_index_pp 與 read（^SOX 等本身的漲跌與哪個指數無關）。都沒有回傳 None——呼叫端寫「資料缺」，不得以 0 代入。"""
    sd = td.get('semis_daily')
    if sd:
        return sd
    for t in alt_tds:
        s = (t or {}).get('semis_daily')
        if s and s.get('as_of') == td.get('trade_date') and s.get('change_pct') is not None and td.get('change_pct') is not None:
            pp = round(s['change_pct'] - td['change_pct'], 2)
            read = ('半導體領跌（落後指數 ≥1.0pp）' if pp <= -1.0 else '半導體領漲（領先指數 ≥1.0pp）' if pp >= 1.0 else '半導體與指數同步（差距 <1.0pp）')
            return {**s, 'vs_index_pp': pp, 'read': read, 'borrowed_from': t.get('symbol')}
    return None


def apply_holding(la, gate, note, td, alt_tds=()):
    """把第一句寫進 last_analysis：holding_action（含 semis_ref）＋ rating 開頭。rating 若已有舊的動作句就換掉，不重複疊加。"""
    ha = holding_action(gate, la['trade_date'], note)
    ha['semis_ref'] = semis_ref(semis_for(td, alt_tds))
    la['holding_action'] = ha
    r = la.get('rating') or ''
    if r.startswith(f'對現有{BASKET}'):
        r = r.split('\n', 1)[1] if '\n' in r else ''
    la['rating'] = ha['text'] + (f'\n{r}' if r else '')
    return ha


def semis_ref(sd):
    """半導體參考一行（today_data 的 semis_daily）；僅供參考，不改水位。"""
    if not sd:
        return '半導體參考：日線資料缺（不得以 0 代入）；不影響上面的水位（水位只看 NDX 收盤與 MA200）。'
    fmt = lambda v: '—' if v is None else f'{v:+.2f}%'  # noqa: E731
    ap = '（近似值，末列由 30m 補）' if sd.get('tail_source') else ''
    src = f"，取自 {sd['borrowed_from']} 同日資料" if sd.get('borrowed_from') else ''
    return (f"半導體參考（{sd['basis']}，資料日 {sd['as_of']}{src}）：日 {fmt(sd['change_pct'])}、對指數 {sd['vs_index_pp']:+.2f}pp（{sd['read']}）、"
            f"5 日 {fmt(sd.get('chg_5d_pct'))}、距 MA200 {fmt(sd.get('vs_ma200_pct'))}{ap}；僅供參考，不改水位。")
