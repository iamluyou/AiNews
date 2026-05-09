#!/usr/bin/env python3
"""
Test web config read/write functionality
"""

import tempfile
import yaml
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config_save_and_load():
    """Test that config saved from web can be loaded by Config.from_yaml"""
    from news_agent.config import Config

    # Test data
    test_config_data = {
        "scheduler": {
            "cron_times": ["08:30", "11:30", "13:47"],
            "timezone": "Asia/Shanghai"
        },
        "email_163": {
            "enabled": True,
            "sender": "test@163.com",
            "password": "testpass",
            "recipients": ["user1@example.com", "user2@example.com"]
        }
    }

    # Create a temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        # Write like our web app would - with quoted cron times
        f.write("""email_163:
  enabled: true
  password: testpass
  recipients:
  - user1@example.com
  - user2@example.com
  sender: test@163.com

scheduler:
  timezone: Asia/Shanghai
  cron_times:
    - '08:30'
    - '11:30'
    - '13:47'
""")
        temp_path = Path(f.name)

    try:
        # Test loading with Config.from_yaml
        config = Config.from_yaml(temp_path)

        # Verify cron times are strings
        assert isinstance(config.scheduler.cron_times, list)
        assert len(config.scheduler.cron_times) == 3
        assert config.scheduler.cron_times[0] == "08:30"
        assert config.scheduler.cron_times[1] == "11:30"
        assert config.scheduler.cron_times[2] == "13:47"
        assert isinstance(config.scheduler.cron_times[0], str)

        print("✓ Config loaded successfully!")
        print(f"  Cron times: {config.scheduler.cron_times}")
        print(f"  All are strings: {all(isinstance(t, str) for t in config.scheduler.cron_times)}")

        return True
    finally:
        temp_path.unlink()


def test_web_config_roundtrip():
    """Test web-style save and load roundtrip"""
    from news_agent.config import Config

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        # Initial config
        yaml.dump({
            "scheduler": {
                "cron_times": ["09:00", "12:00"],
                "timezone": "Asia/Shanghai"
            }
        }, f)
        temp_path = Path(f.name)

    try:
        # Simulate web app saving (with quoted times)
        with open(temp_path, 'w') as f:
            f.write("""scheduler:
  timezone: Asia/Shanghai
  cron_times:
    - '10:30'
    - '14:30'
    - '18:00'
""")

        # Load again
        config = Config.from_yaml(temp_path)

        assert config.scheduler.cron_times == ["10:30", "14:30", "18:00"]
        assert all(isinstance(t, str) for t in config.scheduler.cron_times)

        print("\n✓ Roundtrip test passed!")
        return True
    finally:
        temp_path.unlink()


if __name__ == "__main__":
    print("Testing web config functionality...\n")

    test1_passed = test_config_save_and_load()
    test2_passed = test_web_config_roundtrip()

    if test1_passed and test2_passed:
        print("\n✅ All tests passed! Config works correctly with scheduler.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
