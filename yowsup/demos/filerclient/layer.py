import jsonpickle, json, os, errno, time, datetime
import codecs
from yowsup.layers.interface import YowInterfaceLayer, ProtocolEntityCallback
from yowsup.layers.protocol_messages.protocolentities import TextMessageProtocolEntity
from yowsup.layers.protocol_receipts.protocolentities import OutgoingReceiptProtocolEntity
from yowsup.layers.protocol_acks.protocolentities import OutgoingAckProtocolEntity
import threading


class FilerLayer(YowInterfaceLayer):
    PROP_INBOXPATH  = "org.openwhatsapp.yowsup.prop.filerclient.inboxpath"
    PROP_OUTBOXPATH = "org.openwhatsapp.yowsup.prop.filerclient.outboxpath"
    PROP_SENTPATH   = "org.openwhatsapp.yowsup.prop.filerclient.sentpath"
    EVENT_START     = "org.openwhatsapp.yowsup.event.filer.start"

    def __init__(self):
        super(FilerLayer, self).__init__()
        self.inputThread = threading.Thread(target=self.startOutboxObserverThread)
        self.inputThread.daemon = True

    @ProtocolEntityCallback("message")
    def onMessage(self, messageProtocolEntity):
        # TODO: That should be done in the constructor.
        inboxPath = self.getProp(self.__class__.PROP_INBOXPATH)
        self.mkdir_recursive(inboxPath)

        filename = "%s/%s.jsonpickle" % (inboxPath, messageProtocolEntity.getId())

        print("Received: %s from %s. Writing to file %s" % (
            messageProtocolEntity.getBody(), messageProtocolEntity.getFrom(False), filename))

        with open(filename, "w") as output:
            output.write(jsonpickle.encode(messageProtocolEntity))

        receipt = OutgoingReceiptProtocolEntity(messageProtocolEntity.getId(), messageProtocolEntity.getFrom())
        self.toLower(receipt)

    @ProtocolEntityCallback("receipt")
    def onReceipt(self, entity):
        ack = OutgoingAckProtocolEntity(entity.getId(), "receipt", "delivery")
        self.toLower(ack)

    def sendMessage(self, to, text):
        outgoingMessageProtocolEntity = TextMessageProtocolEntity(text, to=to)
        self.toLower(outgoingMessageProtocolEntity)

    def onEvent(self, layerEvent):
        if layerEvent.getName() == self.__class__.EVENT_START:
            self.inputThread.start()
            return True

    # TODO: Is there a better way of doing this with python?
    def mkdir_recursive(self, path):
        try:
            os.makedirs(path)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise

    def startOutboxObserverThread(self):
        # TODO: That should be done in the constructor.
        outboxPath = self.getProp(self.__class__.PROP_OUTBOXPATH)
        self.mkdir_recursive(outboxPath)
        sentPath = self.getProp(self.__class__.PROP_SENTPATH)
        self.mkdir_recursive(sentPath)

        before = []
        while 1:
            time.sleep(0.1)
            after = dict([(f, None) for f in os.listdir(outboxPath)])
            added = [f for f in after if not f in before]

            for addedFile in added:
                addedFilePath="%s/%s" % (outboxPath, addedFile)

                with codecs.open(addedFilePath, "r", encoding="UTF-8") as fileToRead:
                    fileContent = fileToRead.read()

                print("Going to send: %s with content: %s" % (addedFile, fileContent))
                toAndText = json.loads(fileContent)
                self.sendMessage(toAndText["to"], toAndText["text"])

                os.rename(addedFilePath, "%s/%s-%s" % (sentPath, datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S"), addedFile))