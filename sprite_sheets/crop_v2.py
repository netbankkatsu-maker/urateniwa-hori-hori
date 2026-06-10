"""
スプライトシート クロップ v2 (修正版)
- 最小スペース間隔フィルタで正確なヘッダー検出
- 等分割フォールバック
"""
import os
from PIL import Image

SDIR = os.path.dirname(os.path.abspath(__file__))
ADIR = os.path.join(SDIR, '..', 'assets')
os.makedirs(ADIR, exist_ok=True)

FILES = {
    'player':      'ChatGPT Image 2026年6月9日 20_55_50.png',
    'items':       'ChatGPT Image 2026年6月9日 20_56_22.png',
    'tiles':       'ChatGPT Image 2026年6月9日 20_56_58.png',
    'minerals':    'ChatGPT Image 2026年6月9日 20_57_05.png',
    'buildings':   'ChatGPT Image 2026年6月9日 20_57_11.png',
    'effects':     'ChatGPT Image 2026年6月9日 20_57_17.png',
    'enemies':     'ChatGPT Image 2026年6月9日 20_57_23.png',
    'ui':          'ChatGPT Image 2026年6月9日 20_57_29.png',
    'backgrounds': 'ChatGPT Image 2026年6月9日 20_57_35.png',
    'treasure':    'ChatGPT Image 2026年6月9日 20_57_42.png',
}

saved = []

def load(key):
    p = os.path.join(SDIR, FILES[key])
    img = Image.open(p).convert('RGBA')
    return img

def save_img(img, name, remove_bg=True, min_size=24):
    if remove_bg:
        img = strip_bg(img)
    img = trim(img)
    if img.size[0] < min_size or img.size[1] < min_size:
        return
    path = os.path.join(ADIR, name)
    img.save(path)
    saved.append(name)
    print(f'  → {name}  {img.size[0]}x{img.size[1]}')

def strip_bg(img, thresh=232):
    img = img.convert('RGBA')
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r,g,b,a = pixels[x,y]
            if r > thresh and g > thresh and b > thresh:
                pixels[x,y] = (r,g,b,0)
    return img

def trim(img):
    b = img.getbbox()
    return img.crop(b) if b else img

def find_header_rows(img, expected_n):
    """ヘッダー行を期待行数に基づいて検出（最小スペースフィルタ付き）"""
    w, h = img.size
    px = img.load()
    expected_spacing = h / expected_n
    min_spacing = expected_spacing * 0.55

    # 各行の「ネイビー率」を計算
    navy_rows = []
    for y in range(h):
        cnt = 0
        step = max(1, w // 120)
        total = 0
        for x in range(0, w, step):
            r,g,b = px[x,y][:3]
            # ダークネイビー: 青が赤・緑より明らかに高い
            if r < 100 and g < 100 and b > 50 and b > r + 15 and b > g + 10:
                cnt += 1
            total += 1
        if total > 0 and cnt/total > 0.25:
            navy_rows.append(y)

    # グループ化
    if not navy_rows:
        return _fallback(h, expected_n)
    groups = []
    g = [navy_rows[0]]
    for y in navy_rows[1:]:
        if y - g[-1] <= 5:
            g.append(y)
        else:
            groups.append((g[0], g[-1]))
            g = [y]
    groups.append((g[0], g[-1]))

    # 高さ10px以上のグループだけ残す
    groups = [(ys, ye) for ys, ye in groups if ye - ys >= 10]
    if not groups:
        return _fallback(h, expected_n)

    # 最小スペースフィルタ: 前のヘッダーから min_spacing 以上離れているものだけ採用
    accepted = [groups[0]]
    for gs, ge in groups[1:]:
        if gs - accepted[-1][0] >= min_spacing:
            accepted.append((gs, ge))
        if len(accepted) == expected_n:
            break

    if len(accepted) < expected_n:
        return _fallback(h, expected_n)

    return accepted[:expected_n]

def _fallback(h, n):
    """等分割フォールバック"""
    rh = h // n
    return [(i * rh + 4, i * rh + 42) for i in range(n)]

def content_ranges(header_bands, img_h, pad=3):
    """各ヘッダーの下からコンテンツY範囲を返す"""
    result = []
    for i, (hs, he) in enumerate(header_bands):
        y0 = he + pad
        y1 = header_bands[i+1][0] - pad if i+1 < len(header_bands) else img_h - pad
        result.append((y0, y1))
    return result

def cols_equal(w, n):
    """等分割X座標リスト"""
    cw = w // n
    return [i * cw for i in range(n+1)]

def crop_cell(img, x0, y0, x1, y1, pad=8):
    W, H = img.size
    l = max(0, x0 + pad)
    t = max(0, y0 + pad)
    r = min(W, x1 - pad)
    b = min(H, y1 - pad)
    if r <= l or b <= t:
        return img.crop((max(0,x0), max(0,y0), min(W,x1), min(H,y1)))
    return img.crop((l, t, r, b))

# ============================================================
# SHEET 01: PLAYER
# ============================================================
def process_player():
    print('\n[player]')
    img = load('player')
    w, h = img.size  # 1536x1024

    # 全行を通じてフレーム幅は一定: 1536 / 9 ≈ 171px
    # Row0: idle(1) walk(4) dig(4)  → フレーム番号 0, 1-4, 5-8
    # Row1: jump(3) dmg(3) down(3)  → フレーム番号 0-2, 3-5, 6-8
    # Row2: rescue(3) carry(3) light(3)
    # Row3: pick(3) drill(3) bomb(3)
    FW = w // 9        # フレーム幅 ≈ 170px
    row_h = h // 4
    HDR = 44

    # (row, frame_start, frame_count, name_list)
    sections = [
        (0, 0, 1, ['player_idle']),
        (0, 1, 4, ['player_walk1','player_walk2','player_walk3','player_walk4']),
        (0, 5, 4, ['player_dig1','player_dig2','player_dig3','player_dig4']),
        (1, 0, 3, ['player_jump1','player_jump2','player_jump3']),
        (1, 3, 3, ['player_dmg1','player_dmg2','player_dmg3']),
        (1, 6, 3, ['player_down1','player_down2','player_down3']),
        (2, 0, 3, ['player_rescue1','player_rescue2','player_rescue3']),
        (2, 3, 3, ['player_carry1','player_carry2','player_carry3']),
        (2, 6, 3, ['player_light1','player_light2','player_light3']),
        (3, 0, 3, ['player_pick1','player_pick2','player_pick3']),
        (3, 3, 3, ['player_drill1','player_drill2','player_drill3']),
        (3, 6, 3, ['player_bomb1','player_bomb2','player_bomb3']),
    ]

    for ri, f_start, n_frames, names in sections:
        y0 = ri * row_h + HDR
        y1 = (ri + 1) * row_h - 4
        for fi, name in enumerate(names):
            x0 = (f_start + fi) * FW
            x1 = (f_start + fi + 1) * FW
            cell = crop_cell(img, x0, y0, x1, y1, pad=10)
            save_img(cell, f'{name}.png')

# ============================================================
# SHEET 02: ITEMS
# ============================================================
def process_items():
    print('\n[items]')
    img = load('items')
    w, h = img.size  # 1536x1024

    # 行1: ツルハシLv1-5 (左半分) + ドリルLv1-5 (右半分)
    # 行2: シャベル・爆弾・大型爆弾・ロープ・ランタン・懐中電灯 (6等分)
    # 行3: バッテリー・酸素ボンベ・回復キット・帰還ビーコン・地図・鍵 (6等分)
    HDR = 44
    row_h = h // 3

    # Row0: 左半分5フレーム + 右半分5フレーム
    # Row0ヘッダーはさらに2分割されている
    y0 = HDR
    y1 = row_h - 4
    half = w // 2
    fw5 = half // 5
    for i in range(5):
        cell = crop_cell(img, i*fw5, y0, (i+1)*fw5, y1, pad=12)
        save_img(cell, f'pickaxe_lv{i+1}.png')
    for i in range(5):
        cell = crop_cell(img, half+i*fw5, y0, half+(i+1)*fw5, y1, pad=12)
        save_img(cell, f'drill_lv{i+1}.png')

    # Row1
    y0 = row_h + HDR
    y1 = 2 * row_h - 4
    names1 = ['shovel','bomb','bomb_large','rope_item','lantern','flashlight']
    fw = w // 6
    for i,n in enumerate(names1):
        cell = crop_cell(img, i*fw, y0, (i+1)*fw, y1, pad=14)
        save_img(cell, f'{n}.png')

    # Row2
    y0 = 2*row_h + HDR
    y1 = h - 4
    names2 = ['battery_item','oxygen_item','heal_item','beacon_item','map_item','key_item']
    for i,n in enumerate(names2):
        cell = crop_cell(img, i*fw, y0, (i+1)*fw, y1, pad=14)
        save_img(cell, f'{n}.png')

# ============================================================
# SHEET 03: TILES
# ============================================================
def process_tiles():
    print('\n[tiles]')
    img = load('tiles')
    w, h = img.size

    HDR = 44
    row_h = h // 3

    rows = [
        (7, ['tile_grass','tile_dirt_surface','tile_dirt_soft','tile_dirt_hard',
              'tile_stone','tile_bedrock','tile_cracked']),
        (7, ['tile_indestructible','tile_ore_dirt','tile_cave_bg','tile_underground_wall',
              'tile_underground_floor','tile_slope','tile_ladder']),
        (6, ['tile_rope','tile_platform','tile_water','tile_lava','tile_gas','tile_darkness']),
    ]
    for ri, (n_cols, names) in enumerate(rows):
        y0 = ri*row_h + HDR
        y1 = (ri+1)*row_h - 4
        fw = w // n_cols
        for ci, name in enumerate(names):
            cell = crop_cell(img, ci*fw, y0, (ci+1)*fw, y1, pad=4)
            # タイルは背景除去しない
            save_img(cell, f'{name}.png', remove_bg=False)

# ============================================================
# SHEET 04: MINERALS
# ============================================================
def process_minerals():
    print('\n[minerals]')
    img = load('minerals')
    w, h = img.size

    HDR = 44
    row_h = h // 3

    rows = [
        (7, ['ore_stone','ore_coal','ore_copper','ore_iron','ore_silver','ore_gold','ore_gem']),
        (6, ['ore_ruby','ore_sapphire','ore_emerald','ore_diamond','ore_fossil','ore_bone']),
        (4, ['ore_ancient_coin','ore_ancient_part','ore_mystery','ore_giant']),
    ]
    for ri, (n_cols, names) in enumerate(rows):
        y0 = ri*row_h + HDR
        y1 = (ri+1)*row_h - 4
        fw = w // n_cols
        for ci, name in enumerate(names):
            cell = crop_cell(img, ci*fw, y0, (ci+1)*fw, y1, pad=12)
            save_img(cell, f'{name}.png')

# ============================================================
# SHEET 05: BUILDINGS
# ============================================================
def process_buildings():
    print('\n[buildings]')
    img = load('buildings')
    w, h = img.size

    HDR = 44
    row_h = h // 3

    rows = [
        (5, ['bldg_house','bldg_sell','bldg_upgrade','bldg_warehouse','bldg_craft']),
        (5, ['bldg_quest','bldg_elevator','bldg_lift','bldg_generator','bldg_oxygen']),
        (7, ['bldg_autominer','bldg_autosell','bldg_sign','bldg_crate',
              'bldg_barrel','bldg_workbench','bldg_safe']),
    ]
    for ri, (n_cols, names) in enumerate(rows):
        y0 = ri*row_h + HDR
        y1 = (ri+1)*row_h - 4
        fw = w // n_cols
        for ci, name in enumerate(names):
            cell = crop_cell(img, ci*fw, y0, (ci+1)*fw, y1, pad=10)
            save_img(cell, f'{name}.png')

# ============================================================
# SHEET 06: EFFECTS
# ============================================================
def process_effects():
    print('\n[effects]')
    img = load('effects')
    w, h = img.size

    HDR = 44
    # 行0,1: 等高 / 行2: 発見演出 + 画面揺れ
    row_h_12 = int(h * 0.32)
    row_h_3  = h - 2 * row_h_12

    # Row0: 6エフェクト
    y0, y1 = HDR, row_h_12 - 4
    names0 = ['fx_dig','fx_dust','fx_rock_shards','fx_ore_sparkle','fx_explosion','fx_falling_rock']
    fw = w // 6
    for i,n in enumerate(names0):
        cell = crop_cell(img, i*fw, y0, (i+1)*fw, y1, pad=10)
        save_img(cell, f'{n}.png')

    # Row1: 6エフェクト
    y0, y1 = row_h_12 + HDR, 2*row_h_12 - 4
    names1 = ['fx_gas','fx_water_splash','fx_lava_bubble','fx_heal','fx_upgrade_success','fx_sell']
    for i,n in enumerate(names1):
        cell = crop_cell(img, i*fw, y0, (i+1)*fw, y1, pad=10)
        save_img(cell, f'{n}.png')

    # Row2: 発見演出(1列) + 画面揺れ(4列)
    y0, y1 = 2*row_h_12 + HDR, h - 4
    disc_w = w // 5
    cell = crop_cell(img, 0, y0, disc_w, y1, pad=10)
    save_img(cell, 'fx_discovery.png')
    shake_w = (w - disc_w) // 4
    for i in range(4):
        x0 = disc_w + i*shake_w
        cell = crop_cell(img, x0, y0, x0+shake_w, y1, pad=6)
        save_img(cell, f'fx_shake{i+1}.png', remove_bg=False)

# ============================================================
# SHEET 07: ENEMIES
# ============================================================
def process_enemies():
    print('\n[enemies]')
    img = load('enemies')
    w, h = img.size

    HDR = 44
    row_h = h // 3
    col_w = w // 3

    rows = [
        ['enemy_worm','enemy_bat','enemy_slime'],
        ['enemy_golem','enemy_plant','enemy_mushroom'],
        ['enemy_arobot','enemy_giant_worm','enemy_boss'],
    ]
    for ri, names in enumerate(rows):
        y0 = ri*row_h + HDR
        y1 = (ri+1)*row_h - 4
        for ci, name in enumerate(names):
            cell = crop_cell(img, ci*col_w, y0, (ci+1)*col_w, y1, pad=14)
            save_img(cell, f'{name}.png')

# ============================================================
# SHEET 08: UI
# ============================================================
def process_ui():
    print('\n[ui]')
    img = load('ui')
    w, h = img.size

    # 4行
    HDR = 36
    row_h = h // 4

    # Row0: 5ゲージバー
    y0, y1 = HDR, row_h - 4
    gauges = ['ui_hp_bar','ui_stamina_bar','ui_oxygen_bar','ui_battery_bar','ui_weight_bar']
    fw = w // 5
    for i,n in enumerate(gauges):
        cell = crop_cell(img, i*fw, y0, (i+1)*fw, y1, pad=6)
        save_img(cell, f'{n}.png', remove_bg=False)

    # Row1: お金・深度・ミニマップ・インベントリ・アイテムスロット
    # 不均等幅 → 比率で分割
    y0, y1 = row_h + HDR, 2*row_h - 4
    # お金(1/8) 深度(1/8) ミニマップ(2/8) インベントリ(2/8) アイテムスロット(2/8)
    divisions = [0, w//8, 2*w//8, 4*w//8, 6*w//8, w]
    names1 = ['ui_gold','ui_depth','ui_minimap','ui_inventory_frame','ui_item_slots']
    for i,n in enumerate(names1):
        cell = crop_cell(img, divisions[i], y0, divisions[i+1], y1, pad=4)
        save_img(cell, f'{n}.png', remove_bg=False)

    # Row2: 装備・売却・強化・倉庫・クラフト
    y0, y1 = 2*row_h + HDR, 3*row_h - 4
    names2 = ['ui_equip_slot','ui_sell_screen','ui_upgrade_screen','ui_warehouse_screen','ui_craft_screen']
    fw = w // 5
    for i,n in enumerate(names2):
        cell = crop_cell(img, i*fw, y0, (i+1)*fw, y1, pad=4)
        save_img(cell, f'{n}.png', remove_bg=False)

    # Row3: クエスト・協力マーカー・(ダウン通知+帰還ボタン)・その他
    y0, y1 = 3*row_h + HDR, h - 4
    names3 = ['ui_quest_screen','ui_coop_marker','ui_down_return','ui_misc_buttons']
    fw = w // 4
    for i,n in enumerate(names3):
        cell = crop_cell(img, i*fw, y0, (i+1)*fw, y1, pad=4)
        save_img(cell, f'{n}.png', remove_bg=False)

    # 帰還ボタン: Row3の3列目下半分
    bt_x0 = 2*w//4; bt_y0 = 3*row_h + row_h//2; bt_x1 = 3*w//4
    cell = crop_cell(img, bt_x0, bt_y0, bt_x1, h-4, pad=8)
    save_img(cell, 'ui_return_button.png', remove_bg=False)

# ============================================================
# SHEET 09: BACKGROUNDS
# ============================================================
def process_backgrounds():
    print('\n[backgrounds]')
    img = load('backgrounds')
    w, h = img.size

    HDR = 44
    row_h = h // 3
    col_w = w // 4

    rows = [
        ['bg_sky','bg_backyard','bg_house_interior','bg_shallow_underground'],
        ['bg_bedrock','bg_mine','bg_fossil','bg_underground_lake'],
        ['bg_ancient_ruins','bg_magma','bg_deepest','bg_night_surface'],
    ]
    for ri, names in enumerate(rows):
        y0 = ri*row_h + HDR
        y1 = (ri+1)*row_h - 4
        for ci, name in enumerate(names):
            cell = crop_cell(img, ci*col_w, y0, (ci+1)*col_w, y1, pad=4)
            save_img(cell, f'{name}.png', remove_bg=False)

# ============================================================
# SHEET 10: TREASURE
# ============================================================
def process_treasure():
    print('\n[treasure]')
    img = load('treasure')
    w, h = img.size

    HDR = 44
    row_h = h // 3
    col_w = w // 4

    rows = [
        ['chest_wood','chest_iron','chest_gold','chest_ancient'],
        ['rare_map_piece','rare_dkey','rare_bosskey','rare_machine'],
        ['rare_relic', None, None, None],
    ]
    for ri, names in enumerate(rows):
        y0 = ri*row_h + HDR
        y1 = (ri+1)*row_h - 4
        for ci, name in enumerate(names):
            if not name: continue
            cell = crop_cell(img, ci*col_w, y0, (ci+1)*col_w, y1, pad=14)
            save_img(cell, f'{name}.png')

# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    print('=== クロップ v2 開始 ===')
    process_player()
    process_items()
    process_tiles()
    process_minerals()
    process_buildings()
    process_effects()
    process_enemies()
    process_ui()
    process_backgrounds()
    process_treasure()
    print(f'\n=== 完了: {len(saved)}枚 ===')
