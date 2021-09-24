from __future__ import annotations
import typing as t # noqa
import click, time, datetime
import quickfix as fix
import logger

from spec import fix43

class Application(fix.Application): # type: ignore
    def __init__(self) -> None:
        super().__init__()
        self.sessionID: t.Optional[fix.SessionID] = None
        self.__id: int = 0

    @property
    def id(self) -> str:
        self.__id += 1
        return str(self.__id).zfill(5)

    def onCreate(self, sessionID: fix.SessionID) -> None:
        logger.info(f"{sessionID}")

    def onLogon(self, sessionID: fix.SessionID) -> None:
        self.sessionID = sessionID
        logger.info(f"{sessionID}")

    def onLogout(self, sessionID: fix.SessionID) -> None:
        logger.info(f"{sessionID}")

    def toAdmin(self, message: fix.Message, sessionID: fix.SessionID) -> None:
        logger.debug(f"{sessionID}: {message}")

    def fromAdmin(self, message: fix.Message, sessionID: fix.SessionID) -> None:
        BeginString = fix.BeginString()
        message.getHeader().getField(BeginString)
        BeginString = BeginString.getString()

        if BeginString == fix43.BeginString:
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

        if BeginString == fix43.BeginString:
            fix43.crack(self, message, self.on_Message, sessionID)
        else:
            logger.error(f"unrecognized BeginString: {BeginString}")

        logger.info(f"{sessionID} -> {message}")

    ####################################################################
    def on_Message(self, message: fix.Message, sessionID: fix.SessionID) -> None:
        logger.info(f"unhandled message: `{message}`")

    def on_Heartbeat(self, message: fix43.Heartbeat, sessionID: fix.SessionID) -> None:
        logger.info("Heartbeat callback: {}".format(message))

    def on_Logon(self, message: fix43.Logon, sessionID: fix.SessionID) -> None:
        logger.info("Logon callback: {}".format(message))

    def on_Logout(self, message: fix43.Logon, sessionID: fix.SessionID) -> None:
        logger.info("Logout callback: {}".format(message))

    def on_ExecutionReport(self, message: fix43.ExecutionReport, sessionID: fix.SessionID) -> None:
        logger.info("this is your result for puting new order: {}".format(message))

    # def query_order(self) -> None:
    #     logger.info("query_order...")
    #     assert self.sessionID is not None
    #     msg = fix.Message()
    #     msg.getHeader().setField(fix.MsgType("PRR"))
    #     msg.setField(fix.Account(""))
    #     fix.Session.sendToTarget(msg, self.sessionID)

    def send_order(self) -> None:
        message = fix43.NewOrderSingle(
            cl_ord_id=self.id,
            side=fix43.Side.BUY,
            symbol="MSFT",
            order_qty=1000,
            price=100,
            ord_type=fix43.OrdType.LIMIT,
            handl_inst=fix43.HandlInst.MANUAL_ORDER_BEST_EXECUTION,
            time_in_force=fix43.TimeInForce.DAY,
            transact_time=datetime.datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3],
            text="NewOrderSingle",
        )
        fix.Session.sendToTarget(message.to_raw(), self.sessionID)
        logger.info("Sending new order...")

@click.command()
@click.option("-c", "--cfg", type=str, help="name of configuration file", default="client.cfg")
def main(cfg: str) -> None:
    config = fix.SessionSettings(cfg)
    store = fix.FileStoreFactory(config)
    log = fix.FileLogFactory(config)
    app = Application()
    initiator = fix.SocketInitiator(app, store, config, log)

    initiator.start()

    # app.query_order()
    while True:
        option = input("Please choose 1 for put a new order or 2 to exit!\n")
        if option == '1':
            app.send_order()
            logger.info("Done: Put New Order\n")
        elif option == '2':
            logger.info("exitting...")
            break
        else:
            logger.error("unknown input: {}".format(option))

        time.sleep(1)

    initiator.stop()

if __name__ == "__main__":
    import logging
    logger.setup(logging.INFO)
    main()
