# trading-service

Esqueleto de un sistema de trading automatizado, con capas desacopladas para
que se pueda pasar de backtest a paper trading a trading en vivo sin
reescribir la lógica de estrategia o de riesgo.

## Arquitectura

```
data/       MarketDataProvider: fuente de barras OHLCV. CSVDataProvider y
            SyntheticDataProvider para pruebas offline; CCXTHistoricalDataProvider
            y CCXTLiveDataProvider para datos reales de cripto (público, sin
            API keys). Misma interfaz para histórico y tiempo real.

strategy/   Strategy: recibe una barra, opcionalmente devuelve una Signal.
            No sabe nada de tamaño de posición, cuenta ni ejecución.

risk/       RiskManager: único punto de paso entre una Signal y una Order.
            Calcula el tamaño de posición (según distancia al stop),
            aplica límites de exposición por símbolo y totales, un límite
            de pérdida diaria (pausa blanda) y un kill switch de máximo
            drawdown (halt duro hasta reset manual).

broker/     Broker: ejecuta una Order y devuelve un Fill. PaperBroker
            simula fills al precio de mercado y lleva la cuenta (cash,
            posiciones, PnL realizado). Un broker real implementa la misma
            interfaz.

core/       Tipos compartidos (Bar, Signal, Order, Fill, Position,
            AccountState) y TradingSession, que procesa una barra a la vez
            a través de strategy -> risk manager -> broker.

backtest/   Backtester: reproduce barras históricas a través de una
            TradingSession.

live/       PaperTradingRunner: corre una TradingSession contra un feed en
            vivo (CCXTLiveDataProvider), con logging de cada barra/orden y
            alerta cuando se activa el kill switch.
```

La idea es que **estrategia y riesgo nunca cambian entre backtest, paper
trading y producción** — solo cambia qué `MarketDataProvider` y qué
`Broker` se conectan. `TradingSession` es el código compartido que
garantiza eso.

## Uso rápido

```bash
poetry install

# Backtest de ejemplo (datos sintéticos + cruce de medias móviles)
poetry run python main.py

# Paper trading en vivo contra Binance (datos públicos, sin API keys)
poetry run python paper_trade.py --symbol BTC/USDT --timeframe 1m --poll-interval 30

# Tests (no pegan a la red real: usan un exchange ccxt "fake" inyectado)
poetry run pytest
```

`paper_trade.py` acepta `--exchange` (cualquier id soportado por ccxt),
`--symbol`, `--timeframe`, `--poll-interval`, `--cash`, `--fast-window` y
`--slow-window`. La ejecución es 100% simulada (PaperBroker): no se manda
ninguna orden real al exchange, solo se leen precios públicos.

## Gestión de riesgo (`risk/manager.py`)

Reglas configurables vía `RiskConfig`:

- **Position sizing por volatilidad**: el tamaño de cada operación se
  calcula para que, si se toca el stop, la pérdida sea `risk_per_trade_pct`
  del equity — no un tamaño fijo de contratos/monedas.
- **`max_position_pct`**: tope de exposición a un solo símbolo.
- **`max_total_exposure_pct`**: tope de exposición total del portfolio.
- **`max_daily_loss_pct`**: pausa nuevas operaciones si la pérdida
  realizada del día supera este umbral (se resetea al otro día).
- **`max_drawdown_pct`**: kill switch permanente si el equity cae más de
  este % desde su pico; requiere `reset_halt()` manual para reanudar.

Tanto el `Backtester` como el `PaperTradingRunner` cierran posiciones
automáticamente si el precio toca el `stop_loss_price` de la orden.

## Agregar una estrategia nueva

Implementar `Strategy.on_bar(bar) -> Signal | None` (ver
`strategy/moving_average_crossover.py` como referencia) y enchufarla en
`main.py` o en el backtester — no requiere tocar el resto del sistema.

## ccxt: histórico y paper trading en vivo

`data/ccxt_provider.py` tiene dos proveedores, ambos sobre endpoints
públicos (sin API keys):

- `CCXTHistoricalDataProvider`: pagina `fetch_ohlcv` para traer histórico
  real y correr el `Backtester` contra eso en vez de datos sintéticos.
- `CCXTLiveDataProvider`: hace polling y solo emite una `Bar` cuando una
  vela **cierra** (nunca la que está en formación), para que la estrategia
  vea el mismo tipo de dato en vivo que en backtest. Si el exchange falla
  transitoriamente, loguea un warning y reintenta en el próximo poll en vez
  de tirar abajo la sesión.

`PaperTradingRunner` (`live/paper_runner.py`) conecta ese feed con la misma
`TradingSession` del backtest, y loguea cada barra, cada trade, y un
warning explícito cuando se activa el kill switch de drawdown.

**Nota de este entorno**: esta sesión corre en un sandbox cuya política de
red no permite salir a `api.binance.com` (se probó y devuelve 403 del
proxy de egress). El código está validado con tests que inyectan un
exchange ccxt "fake" (sin red), y con una corrida real que confirmó que
reintenta correctamente ante fallos de conexión — pero no pude hacer un
smoke test contra Binance real desde acá. Corré `python paper_trade.py`
desde tu máquina o un entorno con salida a internet para el primer
paper-trading real.

## Próximos pasos

- **Broker real**: implementar `Broker` contra la API del exchange elegido
  (con API keys, arrancando en testnet) para pasar de paper trading a
  ejecución real — el resto del sistema no cambia.
- **Persistencia**: guardar señales, órdenes, fills y equity curve (DB o
  archivo) para poder auditar y depurar corridas en vivo más allá de los
  logs de consola. También resuelve la continuidad entre reinicios de
  `paper_trade.py`: hoy el estado de cada estrategia (ej. el `deque` de
  cierres de `MovingAverageCrossoverStrategy`) vive solo en memoria del
  proceso, así que un reinicio lo pierde y hay que esperar `slow_window`
  barras nuevas antes de volver a poder operar. Con histórico persistido,
  al arrancar se reconstruye ese estado en memoria a partir de las últimas
  N barras guardadas -- el cálculo del indicador se queda en memoria igual
  que ahora, la base solo resuelve el arranque en frío.
- **Alertas**: notificar (mail/Telegram/etc.) cuando se activa un stop, el
  kill switch, o hay errores de conexión repetidos — hoy solo queda
  logueado.
- **Más estrategias**: el sistema está pensado para tener varias
  estrategias corriendo en paralelo, cada una con su propia asignación de
  riesgo.
