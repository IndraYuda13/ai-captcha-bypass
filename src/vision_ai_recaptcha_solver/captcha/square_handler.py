from __future__ import annotations

from typing import Any

from PIL import Image

from .base_handler import BaseCaptchaHandler


class SquareCaptchaHandler(BaseCaptchaHandler):
    captcha_type = 'square_4x4'

    def solve(self, **kwargs: Any):
        result = kwargs['result']
        round_no = kwargs['round_no']
        provider = kwargs['provider']
        model = kwargs.get('model')
        object_name = kwargs['object_name']
        screenshots_dir = kwargs['screenshots_dir']
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
        cols = 4
        rows = max(1, (tile_count + cols - 1) // cols)
        tile_w = grid_width // cols
        tile_h = grid_height // rows
        selected_tiles: list[int] = []
        append_trace(result, round=round_no, note=f'square entry provider={provider} tiles={tile_count} target={object_name} visionai_fn={visionai_rank_grid_tiles is not None}')

        if provider == 'visionai-local' and visionai_rank_grid_tiles is not None:
            raw_ranked = visionai_rank_grid_tiles(grid_path, object_name, cols)
            append_trace(result, round=round_no, note=f'visionai square raw ranked={raw_ranked}')
            ranked_sorted = sorted(raw_ranked, key=lambda x: x[1], reverse=True)
            for cell_num, confidence in ranked_sorted:
                append_trace(result, round=round_no, note=f'visionai square tile {cell_num - 1} conf={confidence:.4f}')
            selected_tiles = [cell_num - 1 for cell_num, confidence in ranked_sorted if confidence >= 0.7]
            append_trace(result, round=round_no, note=f'visionai square selected={selected_tiles}')

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
