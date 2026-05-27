"""
约束压缩器 — Pi 方法论：给模型最少约束，释放推理能力。

4 个压缩级别：
  L0: 全量 (所有约束，~200字)
  L1: 标准 (硬约束+关键软约束，~100字)
  L2: 精简 (仅硬约束，~50字)
  L3: 极限 (只保留动作禁令，~20字)

用法：
  compressor = ConstraintCompressor()
  for level in ["L0", "L1", "L2", "L3"]:
      result = compressor.compress(constraint_result, level)
      print(result["text"], result["char_count"])
"""

class ConstraintCompressor:
    levels = ["L0", "L1", "L2", "L3"]

    def compress(self, constraint_result: dict, level: str = "L1") -> dict:
        hard = constraint_result.get("hard_constraints", "")
        soft = constraint_result.get("soft_suggestions", "")

        if level == "L0":
            text = hard + ("\n" + soft if soft else "")
        elif level == "L1":
            text = hard
        elif level == "L2":
            # Only keep lines with "不能"/"必须"/"不可"/"已死"/"🔒"
            lines = [l for l in hard.split("\n") if l.strip() and
                     any(kw in l for kw in ["不能用", "不能", "必须", "不可", "已死", "🔒", "失衡", "规则"])]
            text = "\n".join(lines)
        elif level == "L3":
            # Only action-level bans: "不能用X", "必须收#N", "🔒不写Y"
            lines = []
            for l in hard.split("\n"):
                l = l.strip()
                if not l: continue
                if "不能用" in l:
                    lines.append(l)
                elif "必须收" in l:
                    parts = l.split(":", 1)
                    lines.append(parts[0] if len(parts) > 1 else l[:30])
                elif "🔒" in l:
                    lines.append(l[:40])
                elif "失衡" in l:
                    lines.append(l)
            text = "\n".join(lines)
        else:
            text = hard

        return {
            "level": level,
            "text": text,
            "char_count": len(text),
            "line_count": len([l for l in text.split("\n") if l.strip()]),
        }

    def generate_all_levels(self, constraint_result: dict) -> dict:
        """生成所有压缩级别，用于对比测试"""
        return {level: self.compress(constraint_result, level) for level in self.levels}
