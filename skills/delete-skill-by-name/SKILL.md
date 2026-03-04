---
name: delete-skill-by-name
description: Use when you want to remove a local Codex skill by name with safety checks. This skill locates a skill folder under ~/.codex/skills (or a configured skills root), asks for explicit confirmation, and instead of hard-deleting moves the folder into ~/.codex/trash so it can be recovered later.
---

# Delete Skill By Name

## 概览

这个 skill 用于**按名字安全删除本地 Codex skill**，默认行为是：

1. 把目标 skill 对应的目录从 `~/.codex/skills/<skill-name>` 下移出；
2. 不做物理删除，而是**移动到 `~/.codex/trash`（你机器上即 `/Users/felicity/.codex/trash`）文件夹**中；
3. 整个过程带有**二次确认**，避免误删。

适用场景：
- 用户说“删除某个 skill”“移除这个 skill”；  
- 希望清理本地 skills 目录，但又想保留一个可恢复的“回收站”；  
- 需要用名字精确指定要删除的 skill（对应 `~/.codex/skills` 里的子目录名）。

> 默认约定：  
> - skills 根目录：`~/.codex/skills`（可通过环境变量 `CODEX_SKILLS_ROOT` 或脚本参数覆盖）；  
> - 回收站目录：`~/.codex/trash`（在本机即 `/Users/felicity/.codex/trash`）。

---

## 交互流程（在对话中使用）

当使用本 skill 帮用户删除某个 skill 时，遵循以下步骤：

1. **解析 skill 名字**
   - 如果用户已经给出明确名字（例如 `pdf-translate`），直接记下；  
   - 如果只说“把刚才那个 skill 删掉”，必须先追问：  
     - “请给出要删除的 skill 目录名（例如 `pdf-translate`），对应 `~/.codex/skills/<name>` 下的子目录。”

2. **计算路径并检查是否存在**
   - 计算 skills 根目录：
     - 优先使用环境变量 `CODEX_SKILLS_ROOT`；  
     - 否则使用 `~/.codex/skills`。  
   - 拼出目标目录：`<skills-root>/<skill-name>`；  
   - 如果目录不存在或不是目录，停止操作并向用户说明情况。

3. **向用户进行二次确认（必需）**
   - 把即将移动的路径清晰地回显给用户，例如：  
     - “准备把 `~/.codex/skills/pdf-translate` 移动到 `./codex/trash/pdf-translate-YYYYMMDD-HHMMSS`。”  
   - 要求用户**再次输入一次 skill 名字**进行确认：  
     - 提示形式示例：“为避免误操作，请再输入一次要删除的 skill 名字（例如：`pdf-translate`）。任何不完全匹配都视为取消。”
   - 仅当用户重复的名字与原始名字严格一致时才继续执行；否则明确说明“已取消删除”并停止。

4. **规划回收站路径**
   - 回收站根目录：`~/.codex/trash`；  
   - 如果不存在，则创建该目录及其父目录；  
   - 实际目标目录建议追加时间戳，避免重名覆盖，例如：  
     - `~/.codex/trash/<skill-name>-YYYYMMDD-HHMMSS`。

5. **执行移动操作**
   - 在 Codex 环境中，优先调用随 skill 一起提供的脚本：  

     ```bash
     # 在 skill 目录下
     python3 scripts/delete_skill.py "<skill-name>" -y
     ```

   - 或者在对话中通过 shell 工具执行等效命令；  
   - 该脚本会：
     - 检查 `<skills-root>/<skill-name>` 是否存在且为目录；  
     - 确保 `~/.codex/trash` 存在；  
     - 将整个目录移动到 `~/.codex/trash/<skill-name>-<timestamp>`。

6. **向用户回报结果**
   - 明确告知：
     - 实际被移动的原路径；  
     - 回收站中的新路径；  
   - 提醒用户如果误删，可以从 `./codex/trash` 中手动移回原位置。

---

## 脚本：`scripts/delete_skill.py`

本 skill 附带一个 Python 脚本，用于实际执行“按名字删除（移动） skill”的操作。

### 命令行用法

```bash
python3 scripts/delete_skill.py <skill-name> \
  [--skills-root /path/to/skills-root] \
  [--trash-root ~/.codex/trash] \
  [-y] \
  [--dry-run]
```

参数说明：

- `skill-name`（必填）  
  要删除的 skill 目录名，对应 `<skills-root>/<skill-name>`；

- `--skills-root`（可选）  
  skills 根目录，默认：
  - 环境变量 `CODEX_SKILLS_ROOT`；  
  - 否则 `~/.codex/skills`。

- `--trash-root`（可选）  
  回收站根目录，默认 `~/.codex/trash`（在本机即 `/Users/felicity/.codex/trash`）；  
  支持传入其它绝对路径。

- `-y, --yes`（可选）  
  跳过命令行里的交互确认，直接执行移动。  
  在 Codex 自动化场景中，应当先在对话中完成用户确认，再通过 `-y` 调用脚本。

- `--dry-run`（可选）  
  只打印将要执行的移动操作，不做任何修改，适合调试。

### 脚本行为（逻辑概述）

1. 解析命令行参数，确定：
   - skills 根目录；  
   - 目标 skill 目录 `<skills-root>/<skill-name>`；  
   - 回收站根目录 `<trash-root>`。
2. 校验：
   - skills 根目录是否存在；  
   - `<skills-root>/<skill-name>` 是否存在且为目录；
   - 若不存在则退出并返回非零状态码。
3. 构造目标路径：
   - 在 `<trash-root>` 下创建 `<skill-name>-YYYYMMDD-HHMMSS` 目录名作为最终目标；
   - 若 `<trash-root>` 不存在，则先创建父目录。
4. 打印即将执行的移动操作路径（源路径与目标路径）。
5. 若未指定 `-y`，脚本会在命令行中再次询问用户输入 skill 名字用于确认：
   - 仅当输入与 `skill-name` 完全一致时才继续执行；  
   - 否则退出并视为用户取消。
6. 在非 `--dry-run` 模式下，执行目录移动操作（如 `shutil.move`），并在成功后打印最终结果路径。

---

## 在 Codex 中的推荐使用方式

当本 skill 被触发时，遵循以下约束：

1. **永远在对话中完成确认，再用 `-y` 调用脚本**  
   - 不要依赖脚本自己的交互式 `input()` 提示，以免阻塞自动化流程；  
   - 对话确认规则：  
     - 明确展示将被移动的源目录与目标目录；  
     - 要求用户再次输入 skill 名字进行确认。

2. **优先使用默认路径约定**
   - skills 根目录：`~/.codex/skills`；  
   - 回收站根目录：`~/.codex/trash`（在本机即 `/Users/felicity/.codex/trash`）。
   - 仅当用户明确指定其它路径时，才覆盖默认行为。

3. **删除 = 移动，不做物理删除**
   - 本 skill 的语义是“软删除/归档”，而不是 `rm -rf`；  
   - 任何需要永久删除的操作，都应明确提示用户自行在回收站确认后再物理删除。

---

## 快速示例

### 示例 1：删除 `pdf` skill

用户：  
> 请把本地的 `pdf` skill 删掉，但保留个备份。

代理使用本 skill 的推荐流程：

1. 计算路径：
   - skills 根目录：`~/.codex/skills`；  
   - 目标目录：`~/.codex/skills/pdf`；  
   - 回收站：`~/.codex/trash/pdf-YYYYMMDD-HHMMSS`。

2. 在对话中确认：
   - 明确说明将移动 `~/.codex/skills/pdf` → `~/.codex/trash/pdf-YYYYMMDD-HHMMSS`；  
   - 要求用户再次输入 `pdf` 作为确认。

3. 用户确认后，执行脚本：

   ```bash
   cd <包含本 skill 的目录>
   python3 scripts/delete_skill.py pdf -y
   ```

4. 告知用户：
   - skill 已从 `~/.codex/skills/pdf` 移动到 `~/.codex/trash/pdf-YYYYMMDD-HHMMSS`；  
   - 如果需要恢复，只需把该目录移回 `~/.codex/skills/pdf`。
