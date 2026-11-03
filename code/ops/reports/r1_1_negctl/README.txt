本目录不是真实执行快照，而是 R1.1 的**负向对照夹具**。

内容：把 `ops/reports/r1_1/run2_summary.json` 故意改残两处
  1. 删掉 `counts_after.data_quality_issue`
  2. 删掉顶层 `table_delta_inserted`
放进本目录，再用 `--run-dir ops/reports/r1_1_negctl` 跑核验。

目的：证明 V8 的新判据真的会拦（旧实现用 `d.get(t, 0)` 会把缺失当 0，反而"满足"幂等）。
结果：退出码 1，V8 = FAIL，并逐条列出缺了哪些字段。见 `../r1_1/08_negative_control.log`。

真实的 run1/run2 快照在 `../r1_1/`，不要用本目录做任何取证。
