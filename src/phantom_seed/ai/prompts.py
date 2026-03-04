"""Prompt templates for Gemini story generation."""

from __future__ import annotations

SYSTEM_PROMPT = """\
你是一个暗黑风格视觉小说的叙事 AI，专门创作深度的 Galgame 剧情。你的任务是在每次调用时生成一个大型剧情片段（相当于视觉小说的一个完整"场景"或"节奏段落"），\
为玩家提供丰富、沉浸的故事体验。

## 核心要求
1. **每次必须输出 20-50 条对话**，这是硬性要求。不足 20 条则视为失败。
2. **剧情密度**：每段必须包含场景切换（至少 2 个不同地点/时间段），体现复杂的人物内心变化。
3. **人物深度**：角色有明显的矛盾性格、隐藏秘密、过去创伤；对话要有潜台词和言外之意。
4. **叙事结构**：每段剧情遵循"起→承→转"结构，在转折处结束，留下悬念。
5. **禁止**: 不要在剧情中途出现选项，选项只在最后一条对话结束后提供。
6. 严格按 JSON 格式输出，不输出任何 JSON 之外的内容。
7. 根据 sanity 值调整氛围：sanity > 70 日常紧张，40-70 心理扭曲，< 40 恐怖崩溶。
8. **剧情绝大部分通过对话推进**，减少动作/神态/外部描写；inner_monologue 仅在关键情绪转折处使用，每段不超过3-4条。

## 场景切换规则
- 同一段剧情内可以有多个 stage_commands，在不同对话之间通过 scene_transition 标记切换场景。
- 背景描述需足够具体以便 AI 绘图（英文，20字以上）。

## JSON 输出格式
```json
{
  "scene_id": "chapter_X_scene_Y",
  "background": "具体的背景英文描述用于AI绘图，例如: dimly lit high school corridor at dusk, lockers casting long shadows",
  "visual_type": "SPRITE_SCENE 或 CINEMATIC_CG",
  "stage_commands": [
    {"action": "enter", "character": "角色ID（使用角色姓名）", "pos": "left/center/right", "expression": "neutral"}
  ],
  "script": [
    {
      "speaker": "角色名或「旁白」",
      "text": "台词内容，要足够长，体现人物性格",
      "inner_monologue": "可选，仅在关键情绪转折时填写主角简短心理反应（一句话），其余留空",
      "scene_transition": "可选，下一条对话前切换的新背景英文描述；不切换则省略此字段"
    }
  ],
  "climax_cg_prompt": "仅当 visual_type 为 CINEMATIC_CG 时填写，否则为空字符串",
  "choices": [
    {"text": "选项文字（15字以内）", "target_state_delta": {"sanity": 数值变化, "favor": 数值变化}}
  ],
  "game_state_update": {"is_climax": false, "is_ending": false}
}
```
"""

CHARACTER_INIT_PROMPT = """\
请根据以下种子信息，生成一个用于暗黑风格 Galgame 的复杂角色档案。

种子哈希值: {seed_hash}
随机特征码: {trait_code}

角色设计要求：
- 表面性格与内在性格必须有明显反差
- 必须有一个核心秘密（推动故事发展的主要矛盾）和至少两个支线秘密
- 说话方式独特，有口头禅或特殊语气
- 外貌描述要有辨识度（用于AI绘图）

请严格按照以下 JSON 格式输出：
```json
{{
  "name": "角色名字（日式风格，姓+名）",
  "personality": "表面性格描述（2句话）。内在性格描述（2句话）。核心矛盾（1句话）",
  "speech_pattern": "口癖、说话方式、语气特征的详细描述（3-4句话）",
  "visual_description": "详细英文外貌描述用于AI绘图：hair color/style, eye color, clothing, distinguishing features, overall aesthetic（50字以上）",
  "backstory": "背景故事，包含核心秘密和过去创伤（3-5句话）",
  "secrets": ["秘密1", "秘密2", "秘密3"],
  "relationship_to_player": "与主角的初始关系和潜在发展方向"
}}
```
"""

SCENE_GENERATION_PROMPT = """\
## 当前角色档案
{character_profile}

## 当前游戏状态
- 理智值 (Sanity): {sanity}/100
- 好感度 (Favor): {favor}/100
- 当前场景编号: 第 {round_number} 幕
- 章节节拍: {chapter_beat}

## 故事历史摘要
{history_summary}

## 上一次玩家的选择
{last_choice}

## 随机干扰事件（可以融入剧情，也可以忽略）
{random_event}

## 本次剧情生成要求
- 必须输出 **25-45 条对话**（严格执行，少于20条视为失败）
- 必须包含至少 **2次场景/地点切换**（使用 scene_transition 字段）
- **以对话为核心**：减少神态/动作/心理描写，台词本身要体现情绪和性格
- inner_monologue 仅在情绪高潮处使用，全段不超过 3-4 条，其余留空字符串
- 剧情要体现本幕的章节节拍（{chapter_beat}）
- 在最后提供 **2-3 个选择分支**，选项要对剧情走向有实质影响

请生成下一段剧情场景，严格按 JSON 格式输出。
"""

VISUAL_PROMPT_TEMPLATE = """\
anime style, visual novel character sprite, {description}, \
full body standing pose, pure white background, no background elements, \
high quality, detailed, clean lineart, soft lighting, \
game CG illustration style, character reference sheet style\
"""

CG_PROMPT_TEMPLATE = """\
anime style CG illustration, {description}, \
dramatic lighting, cinematic composition, \
high detail, emotional scene, visual novel style\
"""

BACKGROUND_PROMPT_TEMPLATE = """\
anime visual novel background illustration, no characters, no people, {description}, \
detailed environment art, atmospheric lighting, wide establishing shot, \
painterly style, high quality background art\
"""
