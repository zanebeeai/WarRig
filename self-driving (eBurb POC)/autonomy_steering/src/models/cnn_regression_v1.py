from typing import Tuple

import tensorflow as tf


def build_model(model_cfg: dict) -> tf.keras.Model:
    input_cfg = model_cfg["input"]
    resize_h, resize_w = input_cfg["resize_hw"]
    channels = input_cfg["channels"]
    input_shape: Tuple[int, int, int] = (resize_h, resize_w, channels)

    inputs = tf.keras.Input(shape=input_shape, name="image")
    x = inputs

    net_cfg = model_cfg["network"]
    for i in range(net_cfg["conv_blocks"]):
        filters = net_cfg["filters"][i]
        kernel = tuple(net_cfg["kernel_sizes"][i])
        stride = tuple(net_cfg["strides"][i])
        x = tf.keras.layers.Conv2D(filters, kernel, strides=stride, activation="relu")(x)
        x = tf.keras.layers.BatchNormalization()(x)

    x = tf.keras.layers.Flatten()(x)
    for units in net_cfg["dense_units"]:
        x = tf.keras.layers.Dense(units, activation="relu")(x)
        x = tf.keras.layers.Dropout(net_cfg.get("dropout", 0.0))(x)

    outputs = tf.keras.layers.Dense(1, activation="linear", name="theta")(x)
    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="cnn_regression_v1")
    return model
