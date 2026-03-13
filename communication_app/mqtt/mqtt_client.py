"""MQTT Client wrapper around paho-mqtt."""

import logging

import paho.mqtt.client as mqtt

logger = logging.getLogger("comm_app.mqtt")


class MQTTClientWrapper:
    """Thin wrapper around paho-mqtt with app-level callbacks."""

    def __init__(self):
        self._client: mqtt.Client | None = None
        self._connected = False
        self._intentional_disconnect = False
        self._subscriptions: set[str] = set()

        # Callbacks
        self.on_connected: callable = None
        self.on_disconnected: callable = None
        self.on_message_received: callable = None
        self.on_error: callable = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def subscriptions(self) -> set[str]:
        return set(self._subscriptions)

    def connect(self, broker: str, port: int = 1883, client_id: str = "",
                username: str = "", password: str = "") -> None:
        if self._connected:
            return
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        if username:
            self._client.username_pw_set(username, password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        try:
            self._client.connect(broker, port, keepalive=60)
            self._client.loop_start()
        except Exception as e:
            logger.error("MQTT connect failed: %s", e)
            if self.on_error:
                self.on_error(f"MQTT connect failed: {e}")

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self._connected = True
            logger.info("MQTT connected to broker")
            if self.on_connected:
                self.on_connected()
            # Re-subscribe after reconnect
            for topic in self._subscriptions:
                self._client.subscribe(topic)
        else:
            logger.error("MQTT connection refused: %s", reason_code)
            if self.on_error:
                self.on_error(f"MQTT connection refused: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self._connected = False
        logger.info("MQTT disconnected (rc=%s)", reason_code)
        if self._intentional_disconnect:
            if self.on_disconnected:
                self.on_disconnected()
        else:
            logger.info("MQTT unexpected disconnect – paho will auto-reconnect")

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage):
        payload = msg.payload.decode("utf-8", errors="replace")
        logger.debug("MQTT [%s]: %s", msg.topic, payload)
        if self.on_message_received:
            self.on_message_received(msg.topic, payload)

    def subscribe(self, topic: str, qos: int = 0) -> None:
        if not self._connected or not self._client:
            return
        self._client.subscribe(topic, qos)
        self._subscriptions.add(topic)
        logger.info("Subscribed to %s", topic)

    def unsubscribe(self, topic: str) -> None:
        if not self._connected or not self._client:
            return
        self._client.unsubscribe(topic)
        self._subscriptions.discard(topic)
        logger.info("Unsubscribed from %s", topic)

    def publish(self, topic: str, message: str, qos: int = 0) -> None:
        if not self._connected or not self._client:
            return
        self._client.publish(topic, message, qos)
        logger.debug("Published to %s: %s", topic, message)

    def disconnect(self) -> None:
        if not self._client:
            return
        self._connected = False
        # Clear callbacks to prevent stale signals during teardown
        self._client.on_connect = None
        self._client.on_disconnect = None
        self._client.on_message = None
        self._client.loop_stop()
        self._client.disconnect()
        self._client = None
        logger.info("MQTT client disconnected")
