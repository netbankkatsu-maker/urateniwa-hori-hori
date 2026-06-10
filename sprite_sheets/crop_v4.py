"""
スプライトシート クロップ v4
- 背景色 R≈234, G≈231, B≈232 を正確に検出して除去
- フラッドフィルで外縁から背景を塗りつぶす
"""
import os, io, shutil, tempfile
from PIL import Image
import numpy as np
from collections import deque

SDIR = os.path.dirname(os.path.abspath(__file__))
ADIR = os.path.realpath(os.path.join(SDIR, '..', 'assets'))
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

def save_img(img, name, remove_bg=True, min_size=20):
    try:
        if remove_bg:
            img = remove_background(img)
        img = trim(img)
        if img is None:
            return
        w, h = img.size
        if w < min_size or h < min_size:
            return
        # numpy由来の画像を確実にPNGバイト列に変換してから書き込み
        buf = io.BytesIO()
        # 新しいRGBAイメージにコピー (モード・サイズを正規化)
        clean = Image.new('RGBA', (w, h), (0,0,0,0))
        clean.paste(img.convert('RGBA'), (0,0))
        clean.save(buf, format='PNG', optimize=False)
        buf.seek(0)
        data = buf.read()
        # ファイルに書き込み (os.open で低レベルアクセス)
        path = os.path.join(ADIR, name)
        import time
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, 'O_BINARY'): flags |= os.O_BINARY
        # リトライ3回
        for attempt in range(3):
            try:
                fd = os.open(path, flags)
                os.write(fd, data)
                os.close(fd)
                saved.append(name)
                break
            except OSError:
                if attempt < 2:
                    time.sleep(0.05)
                else:
                    raise
    except Exception as e:
        print(f'  !! {name} SKIP: {e}')

def is_bg_pixel(r, g, b, tol=32):
    """背景ピクセル判定: グレー系 / 薄ブルー系 / セパレーター線"""
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    chroma = max_c - min_c
    # グレー背景 (白〜薄グレー)
    if chroma < tol and r > 180 and g > 180 and b > 180:
        return True
    # やや暗いグレー (点線のダッシュ部分)
    if chroma < 25 and r > 130 and g > 130 and b > 130:
        return True
    # 薄いブルーグレー (ChatGPTシートのセパレーター線)
    # B が R や G より少し高く、全体的に明るい
    if b > r - 8 and b > g - 8 and r > 160 and g > 160 and b > 165:
        return True
    # 薄いブルー (セル境界の点線: 例 R=180,G=190,B=220)
    if b > r + 8 and b > g + 4 and r > 150 and g > 155:
        return True
    return False

def floodfill_bg(img):
    """外縁からフラッドフィルで背景を透明化"""
    arr = np.array(img).copy()
    h, w = arr.shape[:2]
    visited = np.zeros((h, w), dtype=bool)
    transparent = np.zeros((h, w), dtype=bool)

    # 境界ピクセルをキューに追加
    q = deque()
    for x in range(w):
        for y in [0, h-1]:
            r,g,b = arr[y,x,0], arr[y,x,1], arr[y,x,2]
            if is_bg_pixel(r,g,b) and not visited[y,x]:
                q.append((y,x)); visited[y,x]=True; transparent[y,x]=True
    for y in range(h):
        for x in [0, w-1]:
            r,g,b = arr[y,x,0], arr[y,x,1], arr[y,x,2]
            if is_bg_pixel(r,g,b) and not visited[y,x]:
                q.append((y,x)); visited[y,x]=True; transparent[y,x]=True

    # フラッドフィル
    while q:
        cy, cx = q.popleft()
        for dy,dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            ny, nx = cy+dy, cx+dx
            if 0<=ny<h and 0<=nx<w and not visited[ny,nx]:
                r,g,b = arr[ny,nx,0], arr[ny,nx,1], arr[ny,nx,2]
                if is_bg_pixel(r,g,b):
                    visited[ny,nx]=True; transparent[ny,nx]=True; q.append((ny,nx))

    arr[:,:,3] = np.where(transparent, 0, arr[:,:,3])
    return Image.fromarray(arr)

def remove_background(img):
    """背景除去: フラッドフィル + 全体スキャン"""
    img = img.convert('RGBA')
    # まずフラッドフィルで外縁背景を除去
    img = floodfill_bg(img)
    # 残った孤立した背景ピクセルも除去
    arr = np.array(img, dtype=np.uint8)
    r,g,b,a = arr[:,:,0],arr[:,:,1],arr[:,:,2],arr[:,:,3]
    # まだ残っているグレー系ピクセルで透明でないものを追加除去
    max_c = np.maximum(np.maximum(r,g),b).astype(np.int16)
    min_c = np.minimum(np.minimum(r,g),b).astype(np.int16)
    chroma = (max_c - min_c).astype(np.uint8)
    still_bg = (chroma < 28) & (r.astype(np.int16) > 185) & (g.astype(np.int16) > 185) & (b.astype(np.int16) > 185) & (a > 0)
    arr[:,:,3] = np.where(still_bg, 0, arr[:,:,3])
    return Image.fromarray(arr)

def trim(img):
    if img is None: return None
    b = img.getbbox()
    if b is None: return None
    return img.crop(b)

def crop_cell(img, x0, y0, x1, y1, pad=12):
    W, H = img.size
    l = max(0, x0+pad); t = max(0, y0+pad)
    r = min(W, x1-pad); b = min(H, y1-pad)
    if r <= l or b <= t: return img.crop((max(0,x0),max(0,y0),min(W,x1),min(H,y1)))
    return img.crop((l,t,r,b))

# ============================================================
# SHEET 01: PLAYER
# ============================================================
def process_player():
    print('[player]')
    img = load('player')
    w, h = img.size  # 1536x1024

    # 実測セクション境界に基づく正確な計算
    # Row0: idle(x=0~172) | walk×4(x=172~852) | dig×4(x=852~1536)
    # Row1-3: 3セクション均等 (512px each), 3フレーム each (170.7px)
    FW9 = w // 9        # 170px (均等フレーム幅)
    FW3 = w // 3        # 512px (3セクション用)
    FW_inner = FW3 // 3 # 170px (各セクション内フレーム)
    row_h = h // 4
    HDR = 48

    # Row0の特殊レイアウト
    IDLE_W = 172      # アイドルセクション幅
    WALK_W = 680      # ウォークセクション幅 (4フレーム×170)
    DIG_W  = w - IDLE_W - WALK_W  # 残り

    row0_sections = [
        (IDLE_W//2, 1, ['player_idle']),  # 中央1フレーム
        (IDLE_W, WALK_W//4, 4, ['player_walk1','player_walk2','player_walk3','player_walk4']),
        (IDLE_W+WALK_W, DIG_W//4, 4, ['player_dig1','player_dig2','player_dig3','player_dig4']),
    ]

    y0 = HDR; y1 = row_h - 6
    # アイドル
    cell = img.crop((12, y0, IDLE_W-12, y1))
    cell = remove_background(cell); cell = trim(cell)
    if cell.size[0]>20: save_img(cell, 'player_idle.png', remove_bg=False)

    # ウォーク4フレーム (セクション境界の点線をスキップするためpad=32)
    fw = WALK_W // 4
    for i, name in enumerate(['player_walk1','player_walk2','player_walk3','player_walk4']):
        pad_l = 60 if i==0 else 18  # walk1のみ左パッドを大きく
        x0b = IDLE_W + i*fw + pad_l; x1b = IDLE_W + (i+1)*fw - 14
        cell = img.crop((x0b, y0, x1b, y1))
        cell = remove_background(cell); cell = trim(cell)
        if cell and cell.size[0]>20: save_img(cell, f'{name}.png', remove_bg=False)

    # ディグ4フレーム
    fw = DIG_W // 4
    for i, name in enumerate(['player_dig1','player_dig2','player_dig3','player_dig4']):
        pad_l = 60 if i==0 else 18
        x0b = IDLE_W+WALK_W + i*fw + pad_l; x1b = IDLE_W+WALK_W + (i+1)*fw - 14
        cell = img.crop((x0b, y0, x1b, y1))
        cell = remove_background(cell); cell = trim(cell)
        if cell.size[0]>20: save_img(cell, f'{name}.png', remove_bg=False)

    # Row1-3: 3セクション×3フレーム
    other_rows = [
        (1, ['player_jump1','player_jump2','player_jump3',
              'player_dmg1','player_dmg2','player_dmg3',
              'player_down1','player_down2','player_down3']),
        (2, ['player_rescue1','player_rescue2','player_rescue3',
              'player_carry1','player_carry2','player_carry3',
              'player_light1','player_light2','player_light3']),
        (3, ['player_pick1','player_pick2','player_pick3',
              'player_drill1','player_drill2','player_drill3',
              'player_bomb1','player_bomb2','player_bomb3']),
    ]
    for ri, names in other_rows:
        y0b = ri*row_h + HDR; y1b = (ri+1)*row_h - 6
        fw = w // 9  # 9フレーム均等
        for fi, name in enumerate(names):
            x0b = fi*fw + 16; x1b = (fi+1)*fw - 16
            cell = img.crop((x0b, y0b, x1b, y1b))
            cell = remove_background(cell); cell = trim(cell)
            if cell.size[0]>20: save_img(cell, f'{name}.png', remove_bg=False)

# ============================================================
# SHEET 02: ITEMS
# ============================================================
def process_items():
    print('[items]')
    img = load('items')
    w, h = img.size
    HDR, row_h = 48, h // 3

    y0, y1 = HDR, row_h-6
    half, fw5 = w//2, w//2//5
    for i in range(5):
        cell = img.crop((i*fw5+16, y0, (i+1)*fw5-16, y1))
        save_img(cell, f'pickaxe_lv{i+1}.png')
    for i in range(5):
        cell = img.crop((half+i*fw5+16, y0, half+(i+1)*fw5-16, y1))
        save_img(cell, f'drill_lv{i+1}.png')

    for row_i, names in [
        (1, ['shovel','bomb','bomb_large','rope_item','lantern','flashlight']),
        (2, ['battery_item','oxygen_item','heal_item','beacon_item','map_item','key_item']),
    ]:
        y0b = row_i*row_h+HDR; y1b = (row_i+1)*row_h-6
        fw = w//6
        for i,n in enumerate(names):
            save_img(img.crop((i*fw+16, y0b, (i+1)*fw-16, y1b)), f'{n}.png')

# ============================================================
# SHEET 03: TILES
# ============================================================
def process_tiles():
    print('[tiles]')
    img = load('tiles')
    w, h = img.size
    HDR, row_h = 48, h//3
    rows = [
        (7, ['tile_grass','tile_dirt_surface','tile_dirt_soft','tile_dirt_hard','tile_stone','tile_bedrock','tile_cracked']),
        (7, ['tile_indestructible','tile_ore_dirt','tile_cave_bg','tile_underground_wall','tile_underground_floor','tile_slope','tile_ladder']),
        (6, ['tile_rope','tile_platform','tile_water','tile_lava','tile_gas','tile_darkness']),
    ]
    for ri,(nc,names) in enumerate(rows):
        y0=ri*row_h+HDR; y1=(ri+1)*row_h-6; fw=w//nc
        for ci,name in enumerate(names):
            save_img(img.crop((ci*fw+8, y0, (ci+1)*fw-8, y1)), f'{name}.png', remove_bg=False)

# ============================================================
# SHEET 04: MINERALS
# ============================================================
def process_minerals():
    print('[minerals]')
    img = load('minerals')
    w, h = img.size
    HDR, row_h = 48, h//3
    rows = [
        (7, ['ore_stone','ore_coal','ore_copper','ore_iron','ore_silver','ore_gold','ore_gem']),
        (6, ['ore_ruby','ore_sapphire','ore_emerald','ore_diamond','ore_fossil','ore_bone']),
        (4, ['ore_ancient_coin','ore_ancient_part','ore_mystery','ore_giant']),
    ]
    for ri,(nc,names) in enumerate(rows):
        y0=ri*row_h+HDR; y1=(ri+1)*row_h-6; fw=w//nc
        for ci,name in enumerate(names):
            save_img(img.crop((ci*fw+16, y0, (ci+1)*fw-16, y1)), f'{name}.png')

# ============================================================
# SHEET 05: BUILDINGS
# ============================================================
def process_buildings():
    print('[buildings]')
    img = load('buildings')
    w, h = img.size
    HDR, row_h = 48, h//3
    rows = [
        (5, ['bldg_house','bldg_sell','bldg_upgrade','bldg_warehouse','bldg_craft']),
        (5, ['bldg_quest','bldg_elevator','bldg_lift','bldg_generator','bldg_oxygen']),
        (7, ['bldg_autominer','bldg_autosell','bldg_sign','bldg_crate','bldg_barrel','bldg_workbench','bldg_safe']),
    ]
    for ri,(nc,names) in enumerate(rows):
        y0=ri*row_h+HDR; y1=(ri+1)*row_h-6; fw=w//nc
        for ci,name in enumerate(names):
            save_img(img.crop((ci*fw+14, y0, (ci+1)*fw-14, y1)), f'{name}.png')

# ============================================================
# SHEET 06: EFFECTS
# ============================================================
def process_effects():
    print('[effects]')
    img = load('effects')
    w, h = img.size
    HDR=48; rh12=int(h*0.32); fw=w//6
    for row_i, names in [
        (0, ['fx_dig','fx_dust','fx_rock_shards','fx_ore_sparkle','fx_explosion','fx_falling_rock']),
        (1, ['fx_gas','fx_water_splash','fx_lava_bubble','fx_heal','fx_upgrade_success','fx_sell']),
    ]:
        y0=row_i*rh12+HDR; y1=(row_i+1)*rh12-6
        for i,n in enumerate(names):
            save_img(img.crop((i*fw+16, y0, (i+1)*fw-16, y1)), f'{n}.png')

    y0=2*rh12+HDR; y1=h-6; dw=w//5
    save_img(img.crop((16, y0, dw-16, y1)), 'fx_discovery.png')
    sw=(w-dw)//4
    for i in range(4):
        save_img(img.crop((dw+i*sw+8, y0, dw+(i+1)*sw-8, y1)), f'fx_shake{i+1}.png', remove_bg=False)

# ============================================================
# SHEET 07: ENEMIES
# ============================================================
def process_enemies():
    print('[enemies]')
    img = load('enemies')
    w, h = img.size
    HDR=48; row_h=h//3; col_w=w//3
    rows = [
        ['enemy_worm','enemy_bat','enemy_slime'],
        ['enemy_golem','enemy_plant','enemy_mushroom'],
        ['enemy_arobot','enemy_giant_worm','enemy_boss'],
    ]
    for ri,names in enumerate(rows):
        y0=ri*row_h+HDR; y1=(ri+1)*row_h-6
        for ci,name in enumerate(names):
            save_img(img.crop((ci*col_w+18, y0, (ci+1)*col_w-18, y1)), f'{name}.png')

# ============================================================
# SHEET 08: UI
# ============================================================
def process_ui():
    print('[ui]')
    img = load('ui')
    w, h = img.size
    HDR=36; row_h=h//4
    for i,n in enumerate(['ui_hp_bar','ui_stamina_bar','ui_oxygen_bar','ui_battery_bar','ui_weight_bar']):
        y0=HDR; y1=row_h-4; fw=w//5
        save_img(img.crop((i*fw+6, y0, (i+1)*fw-6, y1)), f'{n}.png', remove_bg=False)
    divs=[0,w//8,2*w//8,4*w//8,6*w//8,w]
    for i,n in enumerate(['ui_gold','ui_depth','ui_minimap','ui_inventory_frame','ui_item_slots']):
        save_img(img.crop((divs[i]+4, row_h+HDR, divs[i+1]-4, 2*row_h-4)), f'{n}.png', remove_bg=False)
    fw2=w//5
    for i,n in enumerate(['ui_equip_slot','ui_sell_screen','ui_upgrade_screen','ui_warehouse_screen','ui_craft_screen']):
        save_img(img.crop((i*fw2+4, 2*row_h+HDR, (i+1)*fw2-4, 3*row_h-4)), f'{n}.png', remove_bg=False)
    fw3=w//4
    for i,n in enumerate(['ui_quest_screen','ui_coop_marker','ui_down_return','ui_misc_buttons']):
        save_img(img.crop((i*fw3+4, 3*row_h+HDR, (i+1)*fw3-4, h-4)), f'{n}.png', remove_bg=False)
    save_img(img.crop((2*w//4+4, 3*row_h+row_h//2, 3*w//4-4, h-4)), 'ui_return_button.png', remove_bg=False)

# ============================================================
# SHEET 09: BACKGROUNDS
# ============================================================
def process_backgrounds():
    print('[backgrounds]')
    img = load('backgrounds')
    w, h = img.size
    HDR=48; row_h=h//3; col_w=w//4
    rows=[
        ['bg_sky','bg_backyard','bg_house_interior','bg_shallow_underground'],
        ['bg_bedrock','bg_mine','bg_fossil','bg_underground_lake'],
        ['bg_ancient_ruins','bg_magma','bg_deepest','bg_night_surface'],
    ]
    for ri,names in enumerate(rows):
        y0=ri*row_h+HDR; y1=(ri+1)*row_h-4
        for ci,name in enumerate(names):
            save_img(img.crop((ci*col_w+4, y0, (ci+1)*col_w-4, y1)), f'{name}.png', remove_bg=False)

# ============================================================
# SHEET 10: TREASURE
# ============================================================
def process_treasure():
    print('[treasure]')
    img = load('treasure')
    w, h = img.size
    HDR=48; row_h=h//3; col_w=w//4
    rows=[
        ['chest_wood','chest_iron','chest_gold','chest_ancient'],
        ['rare_map_piece','rare_dkey','rare_bosskey','rare_machine'],
        ['rare_relic',None,None,None],
    ]
    for ri,names in enumerate(rows):
        y0=ri*row_h+HDR; y1=(ri+1)*row_h-6
        for ci,name in enumerate(names):
            if not name: continue
            save_img(img.crop((ci*col_w+18, y0, (ci+1)*col_w-18, y1)), f'{name}.png')

if __name__=='__main__':
    print('=== crop v4 ===')
    process_player(); process_items(); process_tiles()
    process_minerals(); process_buildings(); process_effects()
    process_enemies(); process_ui(); process_backgrounds(); process_treasure()
    print(f'=== {len(saved)}枚完了 ===')
