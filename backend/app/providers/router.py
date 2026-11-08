from app.providers.mock_provider import MockProvider


class ProviderRouter:

    def __init__(self):

        self.provider = MockProvider()

    def get_provider(self):

        return self.provider