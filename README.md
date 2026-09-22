# containerlab 検証集

ixia-c、cEOS などを使う containerlab 検証環境を、試験ごとに `labs/` 配下で管理します。各 lab に topology、元の機器設定、Python 試験、結果レポートをまとめます。

## 登録済みの試験

| Lab | 内容 |
|---|---|
| [ixia-c-one-dut](labs/ixia-c-one-dut/README.md) | ixia-c から cEOS 1台を経由する双方向 UDP と転送性能の検証 |

## ディレクトリ方針

```text
labs/<lab-name>/
├── README.md
├── <topology>.yml
├── <device-startup-config>.cfg
├── TEST_REPORT.md
├── tests/
└── clab-<topology-name>/   # containerlab の実行時生成物。Git 管理対象外
```

新しい試験は `labs/<lab-name>/` に追加します。`clab-*`、証明書・秘密鍵、ログ、Python cache は `.gitignore` で除外します。起動・試験コマンドと注意点は各 lab の README を参照してください。

以前からルートにある別試験の topology と設定は、内容を確認して対応する `labs/` フォルダへ移すまでは Git 管理対象外です。
