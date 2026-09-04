"""Trade gateway."""


class TradeGateway:
    def reject_unclean(self) -> None:
        raise RuntimeError("UNCLEAN_INVENTORY")
