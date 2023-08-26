from maxwell.service.config import Config


class TestConfig:
    def test_all(self):
        config = Config.singleton()
        assert config.get_port() == 9091
        assert config.get_workers() == 2
        assert config.get_proc_name() == "maxwell-server-python"
