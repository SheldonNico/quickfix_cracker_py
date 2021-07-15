from __future__ import annotations
import typing as t # noqa
import click, time
import quickfix as fix
import logger

from spec import fix42, fix43

class Application(fix.Application): # type: ignore
    def __init__(self) -> None:
        super().__init__()
        self.__id: int = 0
        self.__oid: int = 0

    @property
    def id(self) -> str:
        self.__id += 1
        return str(self.__id).zfill(5)

    @property
    def oid(self) -> str:
        self.__oid += 1
        return str(self.__oid).zfill(5)

    def onCreate(self, sessionID: fix.SessionID) -> None:
        logger.info(f"{sessionID}")

    def onLogon(self, sessionID: fix.SessionID) -> None:
        logger.info(f"{sessionID}")

    def onLogout(self, sessionID: fix.SessionID) -> None:
        logger.info(f"{sessionID}")

    def toAdmin(self, message: fix.Message, sessionID: fix.SessionID) -> None:
        logger.debug(f"{sessionID}: {message}")

    def fromAdmin(self, message: fix.Message, sessionID: fix.SessionID) -> None:
        BeginString = fix.BeginString()
        message.getHeader().getField(BeginString)
        BeginString = BeginString.getString()

        if BeginString == fix42.BeginString:
            fix42.crack(self, message, self.on_Message, sessionID)
        elif BeginString == fix43.BeginString:
            fix43.crack(self, message, self.on_Message, sessionID)
        else:
            logger.error(f"unrecognized BeginString: {BeginString}")

        logger.info(f"{sessionID}: {message}")

    def toApp(self, message: fix.Message, sessionID: fix.SessionID) -> None:
        logger.debug(f"{sessionID}: {message}")

    def fromApp(self, message: fix.Message, sessionID: fix.SessionID) -> None:
        BeginString = fix.BeginString()
        message.getHeader().getField(BeginString)
        BeginString = BeginString.getString()

        if BeginString == fix42.BeginString:
            fix42.crack(self, message, self.on_Message, sessionID)
        elif BeginString == fix43.BeginString:
            fix43.crack(self, message, self.on_Message, sessionID)
        else:
            logger.error(f"unrecognized BeginString: {BeginString}")

        logger.info(f"{sessionID} -> {message}")

    ####################################################################
    def on_Message(self, message: fix.Message, sessionID: fix.SessionID) -> None:
        logger.info(f"unhandled message: `{message}`")

    def on_fix43_NewOrderSingle(self, message: fix43.NewOrderSingle.NewOrderSingle, sessionID: fix.SessionID) -> None:
        logger.info(f"Got new order: {message}")
        assert message.OrderQty is not None
        assert message.Price is not None
        if message.OrdType != fix.OrdType_LIMIT:
            raise fix.IncorrectTagValue(message.OrdType)
        else:
            pass

        exec_report = fix43.ExecutionReport.ExecutionReport(
            OrderID = self.oid,
            ExecID = self.id,
            OrdStatus = fix.OrdStatus_FILLED,
            Symbol = message.Symbol,
            Side = message.Side,
            CumQty = message.OrderQty,
            AvgPx = message.Price,
            # LastShares = message.OrderQty, # fix43 does not have this field
            LastPx = message.Price,
            ClOrdID = message.ClOrdID,
            OrderQty = message.OrderQty,
            # ExecTransType = fix.ExecTransType_NEW, # fix43 does not have this field
            ExecType = fix.ExecType_FILL,
            LeavesQty = 0,
        )

        try:
            fix.Session.sendToTarget(exec_report.to_raw(), sessionID)
        except fix.SessionNotFound:
            pass

@click.command()
@click.option("-c", "--cfg", type=str, help="name of configuration file", default="server.cfg")
def main(cfg: str) -> None:
    config = fix.SessionSettings(cfg)
    store = fix.FileStoreFactory(config)
    log = fix.FileLogFactory(config)
    app = Application()
    acceptor = fix.SocketAcceptor(app, store, config, log)

    acceptor.start()

    time.sleep(3)
    while True:
        time.sleep(1)

    acceptor.stop()

if __name__ == "__main__":
    import logging
    logger.setup(logging.INFO)
    main()
