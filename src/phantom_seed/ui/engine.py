"""Pygame-CE main engine — handles the game loop, events, and rendering."""

from __future__ import annotations

import logging
import random
import string
from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame

from phantom_seed.ai.protocol import SceneData, VisualType
from phantom_seed.core.coordinator import GameCoordinator
from phantom_seed.core.save_system import BacklogEntry, SaveData, SaveSystem
from phantom_seed.pipeline.async_gen import AsyncPipeline
from phantom_seed.ui.dialogue import DialogueBox
from phantom_seed.ui.fonts import get_font
from phantom_seed.ui.hud import HUD
from phantom_seed.ui.main_menu import MainMenu
from phantom_seed.ui.menu import ChoiceMenu
from phantom_seed.ui.save_menu import SaveMenuOverlay
from phantom_seed.ui.scene import SceneRenderer
from phantom_seed.ui.settings_menu import SettingsOverlay
from phantom_seed.ui.transitions import FadeTransition, FlashTransition, Transition

if TYPE_CHECKING:
    from phantom_seed.config import Config

log = logging.getLogger(__name__)


class GamePhase(Enum):
    MAIN_MENU = auto()
    LOADING = auto()
    DIALOGUE = auto()
    CHOICE = auto()
    TRANSITION = auto()
    ENDING = auto()


class Engine:
    """The main Pygame game engine."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.running = False
        self.phase = GamePhase.MAIN_MENU
        self.clock: pygame.time.Clock | None = None
        self.screen: pygame.Surface | None = None

        # Game
        self.coordinator: GameCoordinator | None = None
        self.pipeline: AsyncPipeline | None = None
        self.current_scene: SceneData | None = None

        # UI components
        self.scene_renderer: SceneRenderer | None = None
        self.dialogue_box: DialogueBox | None = None
        self.choice_menu: ChoiceMenu | None = None
        self.hud: HUD | None = None
        self.transition: Transition | None = None
        self.main_menu: MainMenu | None = None
        self.settings_overlay: SettingsOverlay | None = None

        # Save / overlay
        self.save_system = SaveSystem(config.project_root)
        self.save_overlay: SaveMenuOverlay | None = None

        # Dialogue state
        self._dialogue_index = 0
        # Full backlog of every line seen this run
        self._backlog: list[BacklogEntry] = []
        # Phase before overlay was opened (to restore on close)
        self._pre_overlay_phase = GamePhase.DIALOGUE

        # Fonts
        self._title_font: pygame.font.Font | None = None
        self._loading_font: pygame.font.Font | None = None

        # Loading animation
        self._loading_dots = 0
        self._loading_timer = 0

    def init(self) -> None:
        """Initialize Pygame and all UI components."""
        pygame.init()
        flags = pygame.FULLSCREEN if self.config.fullscreen else 0
        self.screen = pygame.display.set_mode(
            (self.config.screen_width, self.config.screen_height),
            flags,
        )
        pygame.display.set_caption(self.config.title)
        self.clock = pygame.time.Clock()

        sw, sh = self.config.screen_width, self.config.screen_height
        self.scene_renderer = SceneRenderer(sw, sh)
        self.dialogue_box = DialogueBox(sw, sh)
        self.dialogue_box.set_text_speed(self.config.text_speed_ms)
        self.choice_menu = ChoiceMenu(sw, sh)
        self.hud = HUD(sw)
        self.save_overlay = SaveMenuOverlay(sw, sh, self.save_system)
        self.main_menu = MainMenu(sw, sh, self.save_system)
        self.settings_overlay = SettingsOverlay(sw, sh, self.config)

        self._title_font = get_font(48, bold=True)
        self._loading_font = get_font(24)

    def run(self) -> None:
        """Main game loop."""
        self.init()
        self.running = True
        self.phase = GamePhase.MAIN_MENU

        while self.running:
            assert self.clock is not None
            dt = self.clock.tick(self.config.fps)

            self._handle_events()
            self._update(dt)
            self._render()

        pygame.quit()

    # ── Events ──────────────────────────────────────────────────

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            # Settings overlay intercepts all events when active
            assert self.settings_overlay is not None
            if self.settings_overlay.active:
                action = self.settings_overlay.handle_event(event)
                if action == "close":
                    # Sync text speed to dialogue box
                    assert self.dialogue_box is not None
                    self.dialogue_box.set_text_speed(self.config.text_speed_ms)
                return

            # Save overlay intercepts all events when active
            assert self.save_overlay is not None
            if self.save_overlay.active:
                action = self.save_overlay.handle_event(event)
                if action:
                    self._handle_overlay_action(action)
                return

            # Global hotkeys (only when in-game)
            in_game = self.phase in (
                GamePhase.DIALOGUE,
                GamePhase.CHOICE,
                GamePhase.TRANSITION,
            )
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F5 and in_game:
                    self._quicksave()
                    return
                if event.key == pygame.K_F9:
                    self._quickload()
                    return
                if event.key == pygame.K_s and in_game:
                    self._pre_overlay_phase = self.phase
                    self.save_overlay.open_save()
                    return
                if event.key == pygame.K_l:
                    self._pre_overlay_phase = self.phase
                    self.save_overlay.open_load()
                    return
                if event.key == pygame.K_b and in_game:
                    self._pre_overlay_phase = self.phase
                    self.save_overlay.open_backlog(self._backlog)
                    return

            # Right-click context menu
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                self._pre_overlay_phase = self.phase
                self.save_overlay.open_context(event.pos, in_game)
                return

            if self.phase == GamePhase.MAIN_MENU:
                self._handle_main_menu_event(event)
            elif self.phase == GamePhase.DIALOGUE:
                self._handle_dialogue_event(event)
            elif self.phase == GamePhase.CHOICE:
                self._handle_choice_event(event)
            elif self.phase == GamePhase.ENDING:
                self._handle_ending_event(event)

    def _handle_main_menu_event(self, event: pygame.event.Event) -> None:
        assert self.main_menu is not None
        action = self.main_menu.handle_event(event)
        if action == "new_game":
            seed = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
            self._start_game(seed)
        elif action == "continue":
            self._quickload()
        elif action == "load":
            self._pre_overlay_phase = self.phase
            assert self.save_overlay is not None
            self.save_overlay.open_load()
        elif action == "settings":
            assert self.settings_overlay is not None
            self.settings_overlay.open()
        elif action == "exit":
            self.running = False

    def _handle_dialogue_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            assert self.dialogue_box is not None
            if not self.dialogue_box.finished:
                self.dialogue_box.skip()
            else:
                self._advance_dialogue()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            assert self.dialogue_box is not None
            if not self.dialogue_box.finished:
                self.dialogue_box.skip()
            else:
                self._advance_dialogue()

    def _handle_choice_event(self, event: pygame.event.Event) -> None:
        assert self.choice_menu is not None
        if event.type == pygame.MOUSEMOTION:
            self.choice_menu.handle_mouse_move(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            chosen = self.choice_menu.handle_click(event.pos)
            if chosen:
                self.choice_menu.hide()
                # Start generating next scene with the chosen option
                assert self.pipeline is not None
                self.pipeline.request_next(chosen.text, chosen.target_state_delta)
                self.phase = GamePhase.LOADING

    def _handle_ending_event(self, event: pygame.event.Event) -> None:
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            # Return to main menu
            if self.coordinator:
                self.coordinator.state.reset_for_new_run()
            self._backlog.clear()
            self.phase = GamePhase.MAIN_MENU

    # ── Update ──────────────────────────────────────────────────

    def _update(self, dt_ms: int) -> None:
        if self.phase == GamePhase.LOADING:
            self._update_loading(dt_ms)
        elif self.phase == GamePhase.DIALOGUE:
            assert self.dialogue_box is not None
            self.dialogue_box.update(dt_ms)
        elif self.phase == GamePhase.TRANSITION:
            self._update_transition(dt_ms)

        if self.scene_renderer:
            self.scene_renderer.update(dt_ms)

    def _update_loading(self, dt_ms: int) -> None:
        # Animate loading dots
        self._loading_timer += dt_ms
        if self._loading_timer >= 500:
            self._loading_timer = 0
            self._loading_dots = (self._loading_dots + 1) % 4

        # Check if generation is done
        assert self.pipeline is not None
        if self.pipeline.has_result:
            scene = self.pipeline.collect()
            if scene:
                self._apply_scene(scene)
            else:
                # Fallback on error
                from phantom_seed.ai.protocol import FALLBACK_SCENE

                self._apply_scene(FALLBACK_SCENE)

    def _update_transition(self, dt_ms: int) -> None:
        if self.transition:
            self.transition.update(dt_ms)
            if self.transition.done:
                self.transition = None
                self.phase = GamePhase.DIALOGUE

    # ── Save / Load helpers ─────────────────────────────────────

    def _quicksave(self) -> None:
        if not self.coordinator:
            return
        assert self.save_overlay is not None
        self.save_system.save(
            "QUICK",
            self.coordinator,
            self._dialogue_index,
            self._backlog,
            screenshot=self.screen,
        )
        log.info("Quick saved")

    def _quickload(self) -> None:
        data = self.save_system.load("QUICK")
        if data:
            self._restore_from_save(data)
            log.info("Quick loaded")

    def _handle_overlay_action(self, action: str) -> None:
        if action == "close":
            return
        if action == "qsave":
            self._quicksave()
        elif action == "qload":
            self._quickload()
        elif action == "save":
            assert self.save_overlay is not None
            self._pre_overlay_phase = self.phase
            self.save_overlay.open_save()
        elif action == "load":
            assert self.save_overlay is not None
            self._pre_overlay_phase = self.phase
            self.save_overlay.open_load()
        elif action == "backlog":
            assert self.save_overlay is not None
            self._pre_overlay_phase = self.phase
            self.save_overlay.open_backlog(self._backlog)
        elif action.startswith("save:"):
            slot = action.split(":", 1)[1]
            if self.coordinator:
                self.save_system.save(
                    slot,
                    self.coordinator,
                    self._dialogue_index,
                    self._backlog,
                    screenshot=self.screen,
                )
        elif action.startswith("load:"):
            slot = action.split(":", 1)[1]
            data = self.save_system.load(slot)
            if data:
                self._restore_from_save(data)

    def _restore_from_save(self, data: SaveData) -> None:
        # Rebuild coordinator
        self.coordinator = GameCoordinator(self.config)
        self.pipeline = AsyncPipeline(self.coordinator)
        self.save_system.restore_coordinator(data, self.coordinator)

        # Restore renderer
        assert self.scene_renderer is not None
        self.scene_renderer.characters.clear()
        self.scene_renderer.background = None
        self.scene_renderer.bg_path = ""

        if self.coordinator.character and self.coordinator.character_sprite_path:
            self.scene_renderer.set_character_sprite_path(
                self.coordinator.character.name,
                self.coordinator.character_sprite_path,
            )

        # Restore backlog
        self._backlog = [BacklogEntry(**e) for e in data.backlog]

        # Restore scene and dialogue index
        self._dialogue_index = data.dialogue_index
        if self.coordinator.current_scene:
            scene = self.coordinator.current_scene
            self.current_scene = scene
            self.scene_renderer.apply_scene(scene)
            self.phase = GamePhase.DIALOGUE
            self._set_current_dialogue()
        else:
            self.phase = GamePhase.MAIN_MENU

    # ── Scene management ────────────────────────────────────────

    def _start_game(self, seed: str) -> None:
        """Initialize game coordinator and request first scene."""
        self.coordinator = GameCoordinator(self.config)
        self.pipeline = AsyncPipeline(self.coordinator)

        self.phase = GamePhase.LOADING
        self._loading_dots = 0
        self.pipeline.request_init(seed)

    def _apply_scene(self, scene: SceneData) -> None:
        """Apply a new scene to the UI."""
        self.current_scene = scene
        self._dialogue_index = 0

        assert self.scene_renderer is not None
        if self.coordinator and self.coordinator.character:
            self.scene_renderer.set_character_sprite_path(
                self.coordinator.character.name,
                self.coordinator.character_sprite_path,
            )
        self.scene_renderer.apply_scene(scene)

        # Start transition
        if scene.visual_type == VisualType.CINEMATIC_CG:
            self.transition = FlashTransition(600)
        else:
            self.transition = FadeTransition(400)
        self.phase = GamePhase.TRANSITION

        # Start first dialogue
        self._set_current_dialogue()

    def _set_current_dialogue(self) -> None:
        assert self.current_scene is not None
        assert self.dialogue_box is not None
        if self._dialogue_index < len(self.current_scene.script):
            line = self.current_scene.script[self._dialogue_index]
            # Handle mid-scene background transition
            if line.scene_transition and self.scene_renderer and self.coordinator:
                cached = self.coordinator.get_cached_bg(line.scene_transition)
                if cached:
                    from pathlib import Path
                    from phantom_seed.ui.assets import load_image

                    bg = load_image(
                        cached, (self.config.screen_width, self.config.screen_height)
                    )
                    if bg:
                        self.scene_renderer.background = bg
                        self.scene_renderer.bg_path = cached
            self.dialogue_box.set_dialogue(
                line.speaker, line.text, line.inner_monologue
            )
            # Append to backlog
            scene_id = self.current_scene.scene_id if self.current_scene else ""
            entry = BacklogEntry(
                speaker=line.speaker,
                text=line.text,
                inner_monologue=line.inner_monologue,
                scene_id=scene_id,
            )
            # Avoid duplicates when restoring from save
            if not self._backlog or (
                self._backlog[-1].text != line.text
                or self._backlog[-1].speaker != line.speaker
            ):
                self._backlog.append(entry)

    def _advance_dialogue(self) -> None:
        """Move to the next dialogue line, or show choices."""
        assert self.current_scene is not None
        self._dialogue_index += 1
        if self._dialogue_index < len(self.current_scene.script):
            self._set_current_dialogue()
        else:
            # Dialogue done — show choices or check game state
            if self.current_scene.game_state_update.is_ending:
                self.phase = GamePhase.ENDING
            elif self.current_scene.choices:
                assert self.choice_menu is not None
                self.choice_menu.show(self.current_scene.choices)
                self.phase = GamePhase.CHOICE
            else:
                # No choices — auto advance
                assert self.pipeline is not None
                self.pipeline.request_next()
                self.phase = GamePhase.LOADING

    # ── Render ──────────────────────────────────────────────────

    def _render(self) -> None:
        assert self.screen is not None

        if self.phase == GamePhase.MAIN_MENU:
            self._render_main_menu()
        elif self.phase == GamePhase.LOADING:
            self._render_loading()
        elif self.phase in (GamePhase.DIALOGUE, GamePhase.CHOICE, GamePhase.TRANSITION):
            self._render_game()
        elif self.phase == GamePhase.ENDING:
            self._render_ending()

        # Settings overlay always renders on top
        assert self.settings_overlay is not None
        if self.settings_overlay.active:
            self.settings_overlay.render(self.screen)

        # Save overlay always renders on top
        assert self.save_overlay is not None
        if self.save_overlay.active:
            self.save_overlay.render(self.screen)

        pygame.display.flip()

    def _render_main_menu(self) -> None:
        assert self.screen is not None
        assert self.main_menu is not None
        self.main_menu.render(self.screen)

    def _render_loading(self) -> None:
        assert self.screen is not None
        assert self._loading_font is not None

        self.screen.fill((50, 40, 55))

        dots = "." * self._loading_dots
        text = self._loading_font.render(f"正在生成{dots}", True, (220, 190, 210))
        tx = (self.config.screen_width - text.get_width()) // 2
        self.screen.blit(text, (tx, self.config.screen_height // 2 - 15))

    def _render_game(self) -> None:
        assert self.screen is not None

        # Background + sprites
        assert self.scene_renderer is not None
        self.scene_renderer.render(self.screen)

        # Transition overlay
        if self.transition and self.phase == GamePhase.TRANSITION:
            self.transition.render(self.screen, None, None)

        # HUD
        if self.coordinator:
            assert self.hud is not None
            self.hud.render(self.screen, self.coordinator.state.affection)

        # Dialogue
        if self.phase in (GamePhase.DIALOGUE, GamePhase.TRANSITION):
            assert self.dialogue_box is not None
            self.dialogue_box.render(self.screen)

        # Choices
        if self.phase == GamePhase.CHOICE:
            assert self.choice_menu is not None
            self.choice_menu.render(self.screen)

    def _render_ending(self) -> None:
        assert self.screen is not None
        assert self._title_font is not None
        assert self._loading_font is not None

        self.screen.fill((55, 40, 50))

        # "- Fin -"
        fin_text = self._title_font.render("- Fin -", True, (255, 210, 220))
        fx = (self.config.screen_width - fin_text.get_width()) // 2
        self.screen.blit(fin_text, (fx, 280))

        # Thank you message
        thanks = self._loading_font.render("感谢你的游玩", True, (200, 175, 190))
        tx = (self.config.screen_width - thanks.get_width()) // 2
        self.screen.blit(thanks, (tx, 370))

        # Hint
        hint = self._loading_font.render("点击任意处返回主菜单", True, (150, 130, 145))
        hx = (self.config.screen_width - hint.get_width()) // 2
        self.screen.blit(hint, (hx, self.config.screen_height - 100))
