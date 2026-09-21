# Python標準ライブラリ（試験時間の待機処理に使用）
import time

# OTG APIを操作するPython SDK
import snappi


def test_device_endpoint_minimum():
    # ------------------------------------------------------------------
    # Controllerへ接続
    # ------------------------------------------------------------------
    api = snappi.api(
        location="https://clab-ixia-c-one-dut-test-ixia-c:8443",
        verify=False,
    )

    # ------------------------------------------------------------------
    # Config作成
    # ------------------------------------------------------------------
    cfg = api.config()

    # ------------------------------------------------------------------
    # Port作成
    # ------------------------------------------------------------------
    p1 = cfg.ports.add(
        name="p1",
        location="eth1",
    )

    p2 = cfg.ports.add(
        name="p2",
        location="eth2",
    )

    # ------------------------------------------------------------------
    # Device作成
    # ------------------------------------------------------------------
    dev1 = cfg.devices.add(name="Device1")
    dev2 = cfg.devices.add(name="Device2")

    # ------------------------------------------------------------------
    # Device1: Ethernet / IPv4 Interface
    # ------------------------------------------------------------------
    eth1 = dev1.ethernets.add(name="Device1.Ethernet1")
    eth1.connection.port_name = p1.name
    eth1.mac = "00:00:00:00:00:01"

    ip1 = eth1.ipv4_addresses.add(name="Device1.IPv4")
    ip1.address = "10.1.0.1"
    ip1.gateway = "10.1.0.254"
    ip1.prefix = 24

    # ------------------------------------------------------------------
    # Device2: Ethernet / IPv4 Interface
    # ------------------------------------------------------------------
    eth2 = dev2.ethernets.add(name="Device2.Ethernet1")
    eth2.connection.port_name = p2.name
    eth2.mac = "00:00:00:00:00:02"

    ip2 = eth2.ipv4_addresses.add(name="Device2.IPv4")
    ip2.address = "10.2.0.1"
    ip2.gateway = "10.2.0.254"
    ip2.prefix = 24

    # ------------------------------------------------------------------
    # Flow1: Device1 → Device2
    # ------------------------------------------------------------------
    flow1 = cfg.flows.add(name="Device1_to_Device2")

    # Device配下のIPv4 InterfaceをEndpointとして指定
    flow1.tx_rx.device.tx_names = [ip1.name]
    flow1.tx_rx.device.rx_names = [ip2.name]

    eth_f1, ipv4_f1, udp_f1 = flow1.packet.ethernet().ipv4().udp()

    ipv4_f1.src.value = "10.1.0.1"
    ipv4_f1.dst.value = "10.2.0.1"

    udp_f1.src_port.value = 50000
    udp_f1.dst_port.value = 50001

    flow1.size.fixed = 512
    flow1.rate.percentage = 10
    flow1.duration.fixed_seconds.seconds = 10
    flow1.metrics.enable = True

    # ------------------------------------------------------------------
    # Flow2: Device2 → Device1
    # ------------------------------------------------------------------
    flow2 = cfg.flows.add(name="Device2_to_Device1")

    # Device配下のIPv4 InterfaceをEndpointとして指定
    flow2.tx_rx.device.tx_names = [ip2.name]
    flow2.tx_rx.device.rx_names = [ip1.name]


    eth_f2, ipv4_f2, udp_f2 = flow2.packet.ethernet().ipv4().udp()

    ipv4_f2.src.value = "10.2.0.1"
    ipv4_f2.dst.value = "10.1.0.1"

    udp_f2.src_port.value = 50001
    udp_f2.dst_port.value = 50000


    flow2.size.fixed = 512
    flow2.rate.percentage = 10
    flow2.duration.fixed_seconds.seconds = 10
    flow2.metrics.enable = True

    # ------------------------------------------------------------------
    # Config確認
    # ------------------------------------------------------------------
    print(
        "\nCONFIGURATION",
        cfg.serialize(encoding=cfg.JSON),
        sep="\n",
    )

    # ------------------------------------------------------------------
    # Config反映
    # ------------------------------------------------------------------
    api.set_config(cfg)

    # ------------------------------------------------------------------
    # Protocol起動
    # ------------------------------------------------------------------
    state = api.control_state()
    state.protocol.all.state = state.protocol.all.START
    api.set_control_state(state)

    print("Protocol Started")

    # ARP解決待ち
    time.sleep(10)

    # ------------------------------------------------------------------
    # Traffic印加開始
    # ------------------------------------------------------------------
    state = api.control_state()
    state.traffic.flow_transmit.state = (
        state.traffic.flow_transmit.START
    )
    state.traffic.flow_transmit.flow_names = [
        flow1.name,
        flow2.name,
    ]
    api.set_control_state(state)

    print("Traffic Started")

    # ------------------------------------------------------------------
    # Metrics取得
    # ------------------------------------------------------------------
    request = api.metrics_request()
    request.flow.flow_names = [
        flow1.name,
        flow2.name,
    ]

    for _ in range(20):
        metrics = api.get_metrics(request)
        print(metrics)

        if metrics.flow_metrics and all(
            metric.transmit == metric.STOPPED
            for metric in metrics.flow_metrics
        ):
            break

        time.sleep(1)

    # ------------------------------------------------------------------
    # Traffic印加停止
    # ------------------------------------------------------------------
    state = api.control_state()
    state.traffic.flow_transmit.state = (
        state.traffic.flow_transmit.STOP
    )
    state.traffic.flow_transmit.flow_names = [
        flow1.name,
        flow2.name,
    ]
    api.set_control_state(state)

    print("Traffic Stopped")

    # ------------------------------------------------------------------
    # Protocol停止
    # ------------------------------------------------------------------
    state = api.control_state()
    state.protocol.all.state = state.protocol.all.STOP
    api.set_control_state(state)

    print("Protocol Stopped")
