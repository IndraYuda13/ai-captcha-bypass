from __future__ import annotations

from typing import Any

from PIL import Image

from .base_handler import BaseCaptchaHandler


class DynamicCaptchaHandler(BaseCaptchaHandler):
    captcha_type = 'dynamic_3x3'

    def solve(self, **kwargs: Any):
        result = kwargs['result']
        round_no = kwargs['round_no']
        provider = kwargs['provider']
        model = kwargs.get('model')
        object_name = kwargs['object_name']
        screenshots_dir = kwargs['screenshots_dir']
        current_urls = kwargs['current_urls']
        previous_urls = kwargs['previous_urls']
        append_trace = kwargs['append_trace']
        check_tile_for_object = kwargs['check_tile_for_object']
        visionai_rank_grid_tiles = kwargs.get('visionai_rank_grid_tiles')
        composite_dynamic_cells = kwargs.get('composite_dynamic_cells')
        base_grid_img = kwargs.get('base_grid_img')
        non_matching_cache = kwargs['non_matching_cache']

        table = kwargs['table']
        adapter = kwargs['adapter']
        all_tiles = adapter.get_table_tiles(table)
        grid_path = f'{screenshots_dir}/recaptcha_grid_{round_no}.png'
        adapter.capture_element(table, grid_path)
        result.artifacts.append(grid_path)
        grid_img = Image.open(grid_path).convert('RGB')
        grid_width, grid_height = grid_img.size
        tile_count = len(all_tiles)
        cols = 3
        rows = 3
        tile_w = grid_width // cols
        tile_h = grid_height // rows
        selected_tiles: list[int] = []
        next_base_grid = base_grid_img

        def save_tile(idx: int) -> str:
            tile_path = f'{screenshots_dir}/tile_{round_no}_{idx}.png'
            row = idx // cols
            col = idx % cols
            left = col * tile_w
            top = row * tile_h
            right = (col + 1) * tile_w if col < cols - 1 else grid_width
            bottom = (row + 1) * tile_h if row < rows - 1 else grid_height
            grid_img.crop((left, top, right, bottom)).save(tile_path)
            result.artifacts.append(tile_path)
            return tile_path

        def confirm_tiles(candidate_indices: list[int]) -> list[int]:
            confirmed: list[int] = []
            for idx in candidate_indices:
                tile_path = save_tile(idx)
                _idx, should_click = check_tile_for_object((idx, tile_path, object_name, provider, model))
                if should_click:
                    confirmed.append(idx)
            return confirmed

        if provider in ('visionai-local', 'gemini-cli-grid') and visionai_rank_grid_tiles is not None:
            ranked_sorted = sorted(visionai_rank_grid_tiles(grid_path, object_name, cols), key=lambda x: x[1], reverse=True)
            for cell_num, confidence in ranked_sorted:
                append_trace(result, round=round_no, note=f'visionai dynamic tile {cell_num - 1} conf={confidence:.4f}')

            ranked_map = {cell_num - 1: confidence for cell_num, confidence in ranked_sorted}

            if base_grid_img is not None and previous_urls and current_urls and len(current_urls) == len(previous_urls):
                changed_cells = []
                for idx, prev_url in enumerate(previous_urls):
                    if idx < len(current_urls) and current_urls[idx] != prev_url and (idx + 1) not in non_matching_cache:
                        changed_cells.append(idx + 1)
                append_trace(result, round=round_no, note=f'dynamic changed_cells={changed_cells}')
                if changed_cells and composite_dynamic_cells is not None:
                    merged = composite_dynamic_cells(base_grid_img, changed_cells, current_urls, cols)
                    merged.save(grid_path)
                    grid_img = merged
                    ranked_sorted = sorted(visionai_rank_grid_tiles(grid_path, object_name, cols), key=lambda x: x[1], reverse=True)
                    ranked_map = {cell_num - 1: confidence for cell_num, confidence in ranked_sorted}
                    selected_tiles = [cell_num - 1 for cell_num, confidence in ranked_sorted if (cell_num in changed_cells and confidence >= 0.7)]
                    if not selected_tiles:
                        dynamic_candidates = [(cell_num - 1, confidence) for cell_num, confidence in ranked_sorted if cell_num in changed_cells and confidence >= 0.08]
                        dynamic_candidates.sort(key=lambda x: x[1], reverse=True)
                        selected_tiles = [idx for idx, _ in dynamic_candidates[:max(1, min(2, len(dynamic_candidates)))]]
                        if selected_tiles:
                            append_trace(result, round=round_no, note=f'dynamic empty-selection fallback used raw={selected_tiles}')
                    if selected_tiles:
                        confirmed_tiles = confirm_tiles(selected_tiles)
                        if confirmed_tiles:
                            selected_tiles = confirmed_tiles
                            append_trace(result, round=round_no, note=f'dynamic confirmed changed-cell tiles={selected_tiles}')
                        else:
                            append_trace(result, round=round_no, note='dynamic changed-cell confirmation rejected all tiles')
                            selected_tiles = []
                else:
                    selected_tiles = []
            else:
                top3 = ranked_sorted[:3]
                if len(top3) >= 3 and all(conf >= 0.2 for _, conf in top3):
                    selected_tiles = [cell_num - 1 for cell_num, _ in top3]
                    if len(ranked_sorted) >= 4 and ranked_sorted[3][1] >= 0.7:
                        selected_tiles.append(ranked_sorted[3][0] - 1)
                else:
                    backup = [(cell_num - 1, conf) for cell_num, conf in ranked_sorted if conf >= 0.08]
                    backup.sort(key=lambda x: x[1], reverse=True)
                    selected_tiles = [idx for idx, _ in backup[:max(1, min(3, len(backup)))]]
                    append_trace(result, round=round_no, note='dynamic top-level fallback used')

                if selected_tiles:
                    if provider == 'gemini-cli-grid':
                        append_trace(result, round=round_no, note=f'dynamic trusted grid-ranked top-level tiles={selected_tiles}')
                    else:
                        confirmed_tiles = confirm_tiles(selected_tiles)
                        if confirmed_tiles:
                            selected_tiles = confirmed_tiles
                            append_trace(result, round=round_no, note=f'dynamic confirmed top-level tiles={selected_tiles}')
                        else:
                            high_conf_candidates = [idx for idx, conf in sorted(ranked_map.items(), key=lambda x: x[1], reverse=True) if conf >= 0.7]
                            if high_conf_candidates:
                                selected_tiles = high_conf_candidates[:1]
                                append_trace(result, round=round_no, note=f'dynamic fallback kept top high-conf tile={selected_tiles}')
                            else:
                                selected_tiles = []
                                append_trace(result, round=round_no, note='dynamic confirmation rejected all top-level tiles')
                next_base_grid = grid_img.copy()
                for cell_num, _ in ranked_sorted:
                    if (cell_num - 1) not in selected_tiles:
                        non_matching_cache.add(cell_num)

        if not selected_tiles:
            for i in range(tile_count):
                tile_path = save_tile(i)
                _idx, should_click = check_tile_for_object((i, tile_path, object_name, provider, model))
                if should_click:
                    selected_tiles.append(i)

        return sorted(set(selected_tiles)), next_base_grid
