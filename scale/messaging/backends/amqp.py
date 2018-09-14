"""Backend supporting AMQP 0.9.1, specifically targeting RabbitMQ message broker"""





import queue
import logging
from contextlib import closing

from kombu import Connection

from messaging.backends.backend import MessagingBackend

logger = logging.getLogger(__name__)


class AMQPMessagingBackend(MessagingBackend):
    """Backend supporting message passing via AMQP 0.9.1 broker, targeting RabbitMQ"""

    def __init__(self):
        super(AMQPMessagingBackend, self).__init__('amqp')

        # Message retrieval timeout
        self._timeout = 1

    def send_messages(self, messages):
        """See :meth:`messaging.backends.backend.MessagingBackend.send_messages`"""
        with Connection(self._broker_url) as connection:
            with closing(connection.SimpleQueue(self._queue_name)) as simple_queue:
                for message in messages:
                    logger.debug('Sending message of type: %s', message['type'])
                    simple_queue.put(message)

    def receive_messages(self, batch_size):
        """See :meth:`messaging.backends.backend.MessagingBackend.receive_messages`"""
        with Connection(self._broker_url) as connection:
            with closing(connection.SimpleQueue(self._queue_name)) as simple_queue:
                for _ in range(batch_size):
                    try:
                        message = simple_queue.get(timeout=self._timeout)

                        # Accept success back via generator send
                        success = yield message.payload
                        if success:
                            message.ack()
                    except queue.Empty:
                        # We've reached the end of the queue... exit loop
                        break
