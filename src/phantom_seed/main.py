"""Entry point for Phantom Seed."""

from __future__ import annotations

import logging
import sys


def main() -> None:
    """Launch the Phantom Seed game."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Check for API key
    from phantom_seed.config import Config

    config = Config()
    if not config.gemini_api_key:
        print("ERROR: 请设置 GEMINI_API_KEY")
        print("  方式1: 在项目根目录创建 .env 文件，写入 GEMINI_API_KEY=your_key_here")
        print("  方式2: set GEMINI_API_KEY=your_key_here  (Windows)")
        print("  方式3: export GEMINI_API_KEY=your_key_here  (Linux/Mac)")
        sys.exit(1)

    from phantom_seed.ui.engine import Engine

    engine = Engine(config)
    engine.run()


if __name__ == "__main__":
    main()
