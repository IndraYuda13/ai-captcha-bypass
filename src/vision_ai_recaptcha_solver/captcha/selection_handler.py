from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from .base_handler import BaseCaptchaHandler


class SelectionCaptchaHandler(BaseCaptchaHandler):
    captcha_type = 'selection_3x3'

    def solve(self, **kwargs: Any):
        result = kwargs['result']
        round_no = kwargs['round_no']
        driver = kwargs['driver']
        provider = kwargs['provider']
        model = kwargs.get('model')
        object_name = kwargs['object_name']
        screenshots_dir = kwargs['screenshots_dir']
        current_urls = kwargs['current_urls']
        append_trace = kwargs['append_trace']
        check_tile_for_object = kwargs['check_tile_for_object']
        visionai_rank_grid_tiles = kwargs.get('visionai_rank_grid_tiles')

        table = kwargs['table']
        adapter = kwargs['adapter']
        all_tiles = adapter.get_table_tiles(table)
        grid_path = f'{screenshots_dir}/recaptcha_grid_{round_no}.png'
        adapter.capture_element(table, grid_path)
        result.artifacts.append(grid_path)
        grid_img = Image.open(grid_path).convert('RGB')
        grid_width, grid_height = grid_img.size
        tile_count = len(all_tiles)
        cols = 4 if tile_count == 16 else 3
        rows = max(1, (tile_count + cols - 1) // cols)
        tile_w = grid_width // cols
        tile_h = grid_height // rows
        selected_tiles: list[int] = []
        append_trace(result, round=round_no, note=f'selection entry provider={provider} cols={cols} tiles={tile_count} visionai_fn={visionai_rank_grid_tiles is not None}')

        if provider == 'visionai-local' and visionai_rank_grid_tiles is not None:
            raw_ranked = visionai_rank_grid_tiles(grid_path, object_name, cols)
            append_trace(result, round=round_no, note=f'visionai raw ranked={raw_ranked}')
            ranked = sorted(raw_ranked, key=lambda x: x[1], reverse=True)
            for cell_num, confidence in ranked:
                append_trace(result, round=round_no, note=f'visionai tile {cell_num - 1} conf={confidence:.4f}')
            if cols == 4:
                selected_tiles = [cell_num - 1 for cell_num, confidence in ranked if confidence >= 0.7]
                append_trace(result, round=round_no, note=f'visionai 4x4 selected={selected_tiles}')
            else:
                top3 = ranked[:3]
                append_trace(result, round=round_no, note=f'visionai top3={top3}')
                if len(top3) >= 3 and all(conf >= 0.2 for _, conf in top3):
                    selected_tiles = [cell_num - 1 for cell_num, _ in top3]
                    if len(ranked) >= 4 and ranked[3][1] >= 0.7:
                        selected_tiles.append(ranked[3][0] - 1)
                    append_trace(result, round=round_no, note=f'visionai 3x3 selected={selected_tiles}')
                else:
                    backup = [(cell_num - 1, conf) for cell_num, conf in ranked if conf >= 0.08]
                    backup.sort(key=lambda x: x[1], reverse=True)
                    selected_tiles = [idx for idx, _ in backup[:max(1, min(3, len(backup)))]]
                    append_trace(result, round=round_no, note=f'selection fallback used backup={backup} selected={selected_tiles}')

        if not selected_tiles:
            for i in range(tile_count):
                tile_path = f'{screenshots_dir}/tile_{round_no}_{i}.png'
                row = i // cols
                col = i % cols
                left = col * tile_w
                top = row * tile_h
                right = (col + 1) * tile_w if col < cols - 1 else grid_width
                bottom = (row + 1) * tile_h if row < rows - 1 else grid_height
                grid_img.crop((left, top, right, bottom)).save(tile_path)
                result.artifacts.append(tile_path)
                _idx, should_click = check_tile_for_object((i, tile_path, object_name, provider, model))
                if should_click:
                    selected_tiles.append(i)

        return sorted(set(selected_tiles))
