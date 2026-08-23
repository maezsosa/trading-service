from __future__ import annotations

from dataclasses import dataclass, field

from core.types import AccountState, Order, Side, Signal


@dataclass
class RiskConfig:
    """Configurable risk rules. Tune per account/strategy risk appetite."""

    # Fraction of equity risked on a single trade, sized via the stop distance.
    risk_per_trade_pct: float = 0.01
    # Used when a signal doesn't specify its own stop.
    default_stop_loss_pct: float = 0.02
    # Max fraction of equity allowed in a single symbol.
    max_position_pct: float = 0.20
    # Max fraction of equity allowed across all open positions combined.
    max_total_exposure_pct: float = 0.60
    # Soft pause: no new trades once today's realized loss exceeds this fraction of peak equity.
    max_daily_loss_pct: float = 0.03
    # Hard kill switch: permanently halt (until manually reset) past this drawdown from peak equity.
    max_drawdown_pct: float = 0.15
    # Maps symbol -> group name for symbols that move together (e.g. BTC/ETH
    # both "crypto-majors"). A symbol not listed here is its own singleton
    # group. Doesn't attempt to infer correlation statistically -- it's an
    # explicit, honest declaration rather than a possibly-wrong estimate.
    correlated_groups: dict[str, str] = field(default_factory=dict)
    # Max fraction of equity allowed combined across one correlated group,
    # tighter than max_total_exposure_pct so two correlated symbols can't
    # each sit near the total cap and add up to a single undiversified bet.
    # None disables this check entirely.
    max_group_exposure_pct: float | None = None


class RiskManager:
    """Gatekeeper between strategy signals and order execution.

    Every signal must pass through validate(); nothing reaches the broker
    without going through position sizing, exposure limits, the daily loss
    pause, and the drawdown kill switch.
    """

    def __init__(self, config: RiskConfig):
        self.config = config
        self.halted = False
        self.halt_reason: str | None = None

    def reset_halt(self) -> None:
        """Manually clear the kill switch after a human has reviewed the account."""
        self.halted = False
        self.halt_reason = None

    def _group_of(self, symbol: str) -> str:
        return self.config.correlated_groups.get(symbol, symbol)

    def validate(self, signal: Signal, account: AccountState, mark_price: float) -> Order | None:
        equity = account.equity({signal.symbol: mark_price})
        account.equity_peak = max(account.equity_peak, equity)

        # Kill switch primero: es permanente (hasta reset_halt() manual), así
        # que si ya se activó no tiene sentido seguir evaluando nada más.
        if account.equity_peak > 0:
            drawdown = (account.equity_peak - equity) / account.equity_peak
            if drawdown >= self.config.max_drawdown_pct:
                self.halted = True
                self.halt_reason = f"max drawdown breached: {drawdown:.2%}"

        if self.halted:
            return None

        # Pausa diaria: a diferencia del kill switch, esto se resetea solo al
        # otro día (ver TradingSession.process_bar) -- no marca self.halted.
        if account.equity_peak > 0 and account.realized_pnl_today < 0:
            daily_loss_pct = abs(account.realized_pnl_today) / account.equity_peak
            if daily_loss_pct >= self.config.max_daily_loss_pct:
                return None

        if mark_price <= 0:
            return None

        stop_pct = signal.stop_loss_pct or self.config.default_stop_loss_pct
        stop_distance = mark_price * stop_pct
        if stop_distance <= 0:
            return None

        # Sizing por riesgo, no por capital: la cantidad se calcula para que
        # SI se toca el stop, la pérdida sea exactamente risk_per_trade_pct
        # del equity -- no un tamaño fijo de unidades ni un % fijo de capital.
        # Un stop más ajustado (stop_distance chico) da una posición más
        # grande; un stop más flojo, una más chica, para el mismo riesgo.
        risk_amount = equity * self.config.risk_per_trade_pct
        quantity = risk_amount / stop_distance

        max_position_value = equity * self.config.max_position_pct
        quantity = min(quantity, max_position_value / mark_price)

        # Cada posición se valúa a SU PROPIO precio (avg_entry_price), no al
        # mark_price de la señal actual -- si no, la exposición de cualquier
        # otro símbolo quedaría mal calculada apenas su precio se aleje del
        # de la señal que se está evaluando ahora mismo (bug ya corregido).
        current_exposure = sum(
            abs(position.quantity) * (mark_price if position.symbol == signal.symbol else position.avg_entry_price)
            for position in account.positions.values()
            if position.is_open
        )
        remaining_exposure = equity * self.config.max_total_exposure_pct - current_exposure
        if remaining_exposure <= 0:
            return None
        quantity = min(quantity, remaining_exposure / mark_price)

        # Mismo criterio de valuación que arriba, pero sumando solo las
        # posiciones del mismo grupo correlacionado que la señal.
        if self.config.max_group_exposure_pct is not None:
            signal_group = self._group_of(signal.symbol)
            current_group_exposure = sum(
                abs(position.quantity) * (mark_price if position.symbol == signal.symbol else position.avg_entry_price)
                for position in account.positions.values()
                if position.is_open and self._group_of(position.symbol) == signal_group
            )
            remaining_group_exposure = equity * self.config.max_group_exposure_pct - current_group_exposure
            if remaining_group_exposure <= 0:
                return None
            quantity = min(quantity, remaining_group_exposure / mark_price)

        if quantity <= 0:
            return None

        stop_loss_price = (
            mark_price - stop_distance if signal.side == Side.BUY else mark_price + stop_distance
        )

        take_profit_price = None
        if signal.take_profit_pct:
            take_profit_distance = mark_price * signal.take_profit_pct
            take_profit_price = (
                mark_price + take_profit_distance
                if signal.side == Side.BUY
                else mark_price - take_profit_distance
            )

        return Order(
            timestamp=signal.timestamp,
            symbol=signal.symbol,
            side=signal.side,
            quantity=quantity,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            limit_price=signal.limit_price,
        )
