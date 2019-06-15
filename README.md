# MoneyForward Stock updater
## What's This?
MoneyForwardで米ドル建て外国株式の現物資産を前取引日の終値と現在の為替でアップデートします。

## Preparation
### MoneyForward
次のフォーマットで株式(現物)の資産を手動追加しておきます。

```
<ハイフン以外の任意の文字列>-<tick>-<株式数>
例: MYSTOCK201902-AAPL-1
```

### Alphavantage
株価取得のため、AlphavantageのAPIを使っています。以下からAlphavantageのAPIキーを取得しておきます。
- https://www.alphavantage.co/support/#api-key

### Environment Variables
mf.pyでは以下の環境変数を用います。
- MF_ID: MoneyForwardのユーザ名
- MF_PASS: MoneyForwardのパスワード
- ALPHA_VANTAGE_API_KEY: AlphavantageのAPIKEY

## Execution
普通にDockerfileを元に作成されたDockerを実行すればOKです。
