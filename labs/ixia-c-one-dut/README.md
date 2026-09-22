# ixia-c + cEOS 検証環境

containerlab で ixia-c one と Arista cEOSLab を起動し、cEOS を経由する双方向 UDP トラフィックを snappi で検証する環境です。

## Topology

[Topology 定義](ixia-c-one-dut-test.yml)は ixia-c と cEOS をそれぞれ1台使用し、2本のデータリンクで直結します。cEOS の起動設定の原本は [ceos.cfg](ceos.cfg) です。

```text
ixia-c eth1 (10.1.0.1/24) ── cEOS Ethernet1 (10.1.0.254/24)
ixia-c eth2 (10.2.0.1/24) ── cEOS Ethernet2 (10.2.0.254/24)
```

cEOS は Ethernet1 と Ethernet2 の間で IPv4 をルーティングします。管理 IP は deploy 時に割り当てられるため、固定値を前提にせず `containerlab inspect` で確認してください。

## 起動と状態確認

WSL ローカル Docker Engine に接続した状態で、リポジトリのルートから実行します。以前のルート配置で起動したコンテナが稼働中なら、同名の lab を新しいパスから重ねて deploy しないでください。Docker Desktop の WSL Integration 側の daemon に接続すると、containerlab が作成した Linux bridge を WSL から参照できず deploy に失敗することがあります。

```bash
docker version
containerlab deploy -t labs/ixia-c-one-dut/ixia-c-one-dut-test.yml
containerlab inspect -t labs/ixia-c-one-dut/ixia-c-one-dut-test.yml
docker ps
```

`docker version` の Server が意図した WSL ローカル Engine であることを確認してください。deploy はコンテナ・ネットワークと `labs/ixia-c-one-dut/clab-ixia-c-one-dut-test/` 以下の実行時ファイルを作成・更新します。この実行時ディレクトリ全体を Git 管理対象から外しています。検証レポートとレート比較スクリプトは、この lab のソースディレクトリに保存しています。

## トラフィック試験

[tests/clab-device-endpoint.py](tests/clab-device-endpoint.py) は元の snappi 例をコピーしたものです。snappi と pytest を利用できる Python 環境から実行します。

```bash
python -m pytest -s labs/ixia-c-one-dut/tests/clab-device-endpoint.py
```

この試験は ixia-c に OTG 設定を投入し、512バイトの双方向 UDP を10秒間、各方向10%で送信します。既存の ixia-c 試験設定がある場合は上書きされるため、ほかの試験が動いていないことを確認してから実行してください。レート比較で実際に使用した補助スクリプトと注意点は [rate-sweep/README.md](tests/rate-sweep/README.md) を参照してください。

## 検証結果

Docker 接続障害の復旧経緯、Tx/Rx、損失率、cEOS の InDiscards、Etba CPU の分析は [TEST_REPORT.md](TEST_REPORT.md) に記録しています。
