import argparse
import json
from pathlib import Path

import cv2


def find_template(
    main_img,
    template_path,
    threshold=0.8,
    strict=False,
    edge_threshold=0.45,
    focus_threshold=0.82,
):
    """Copy of the runtime template matching logic from main.py."""
    template = cv2.imread(str(template_path))
    if template is None:
        raise FileNotFoundError(f"找不到模板文件: {template_path}")

    th, tw = template.shape[:2]

    if strict:
        main_match_img = cv2.cvtColor(main_img, cv2.COLOR_BGR2GRAY)
        template_match_img = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    else:
        main_match_img = main_img
        template_match_img = template

    result = cv2.matchTemplate(main_match_img, template_match_img, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    matched = max_val >= threshold
    edge_score = None
    focus_score = None
    fail_reason = None

    if matched and strict:
        x, y = max_loc
        gray_patch = main_match_img[y : y + th, x : x + tw]
        if gray_patch.shape[:2] != template_match_img.shape[:2]:
            matched = False
            fail_reason = "matched_area_out_of_range"
        else:
            patch_edges = cv2.Canny(gray_patch, 50, 150)
            template_edges = cv2.Canny(template_match_img, 50, 150)
            edge_result = cv2.matchTemplate(
                patch_edges, template_edges, cv2.TM_CCOEFF_NORMED
            )
            _, edge_score, _, _ = cv2.minMaxLoc(edge_result)

            focus_width = max(1, int(tw * 0.62))
            focus_patch = gray_patch[:, :focus_width]
            focus_template = template_match_img[:, :focus_width]
            focus_result = cv2.matchTemplate(
                focus_patch, focus_template, cv2.TM_CCOEFF_NORMED
            )
            _, focus_score, _, _ = cv2.minMaxLoc(focus_result)

            if edge_score < edge_threshold:
                matched = False
                fail_reason = "edge_score_below_threshold"
            elif focus_score < focus_threshold:
                matched = False
                fail_reason = "focus_score_below_threshold"

    elif not matched:
        fail_reason = "confidence_below_threshold"

    center_x = max_loc[0] + tw // 2
    center_y = max_loc[1] + th // 2
    return {
        "matched": matched,
        "fail_reason": fail_reason,
        "top_left": [int(max_loc[0]), int(max_loc[1])],
        "center": [int(center_x), int(center_y)],
        "template_size": [int(tw), int(th)],
        "confidence": float(max_val),
        "threshold": float(threshold),
        "strict": bool(strict),
        "edge_score": None if edge_score is None else float(edge_score),
        "edge_threshold": float(edge_threshold),
        "focus_score": None if focus_score is None else float(focus_score),
        "focus_threshold": float(focus_threshold),
    }


def draw_result(screen_img, result, output_path):
    output_img = screen_img.copy()
    x, y = result["top_left"]
    tw, th = result["template_size"]
    color = (0, 255, 0) if result["matched"] else (0, 0, 255)
    cv2.rectangle(output_img, (x, y), (x + tw, y + th), color, 2)
    cv2.circle(output_img, tuple(result["center"]), 4, color, -1)
    cv2.imwrite(str(output_path), output_img)


def parse_args():
    parser = argparse.ArgumentParser(description="测试指尖无双当前模板匹配方法")
    parser.add_argument(
        "--screen",
        "--image",
        dest="screen",
        required=True,
        help="待检测截图路径，--image 是兼容别名",
    )
    parser.add_argument("--template", required=True, help="模板图片路径")
    parser.add_argument("--strict", action="store_true", help="启用严格匹配")
    parser.add_argument("--threshold", type=float, default=0.8, help="主匹配阈值")
    parser.add_argument("--edge-threshold", type=float, default=0.45, help="边缘匹配阈值")
    parser.add_argument("--focus-threshold", type=float, default=0.82, help="左侧重点区域阈值")
    parser.add_argument("--output", help="保存标注结果图片路径")
    return parser.parse_args()


def main():
    args = parse_args()
    screen_path = Path(args.screen)
    template_path = Path(args.template)

    screen_img = cv2.imread(str(screen_path))
    if screen_img is None:
        raise FileNotFoundError(f"找不到截图文件: {screen_path}")

    result = find_template(
        screen_img,
        template_path,
        threshold=args.threshold,
        strict=args.strict,
        edge_threshold=args.edge_threshold,
        focus_threshold=args.focus_threshold,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.output:
        draw_result(screen_img, result, Path(args.output))
        print(f"已保存标注图片: {args.output}")


if __name__ == "__main__":
    main()
