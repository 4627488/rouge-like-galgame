"""Scene generation prompt template."""

from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate

from phantom_seed.ai.prompts.system import SYSTEM_MESSAGE

_SCENE_HUMAN = HumanMessagePromptTemplate.from_template(
    """\
## 当前角色档案
{character_profile}

## 当前游戏状态
- 好感度 (Affection): {affection}/100
- 当前场景编号: 第 {round_number} 幕
- 章节节拍: {chapter_beat}

## 故事历史摘要
{history_summary}

## 上一次玩家的选择
{last_choice}

## 随机小插曲（可以融入剧情，也可以忽略）
{random_event}

## 本次剧情生成要求
- 必须输出 **25-45 条对话**（严格执行，少于20条视为失败）
- 必须包含至少 **2次场景/地点切换**（使用 scene_transition 字段）
- **以对话为核心**：减少神态/动作/心理描写，台词本身要体现情绪和性格
- inner_monologue 仅在心动高潮处使用，全段不超过 3-4 条，其余留空字符串
- 剧情要体现本幕的章节节拍（{chapter_beat}）
- 基调是温馨浪漫的成人恋爱故事，允许有小冲突和误会，但整体基调积极向上
- 【强制约束】所有角色均为 18 岁以上大学生或成年人，不得出现任何涉及未成年人的浪漫或亲密内容
- 在最后提供 **2-3 个选择分支**，选项要对剧情走向有实质影响

请生成下一段剧情场景，严格按 JSON 格式输出。"""
)

SCENE_PROMPT = ChatPromptTemplate.from_messages(
    [
        SYSTEM_MESSAGE,
        _SCENE_HUMAN,
    ]
)
