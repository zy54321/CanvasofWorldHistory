R1.2 —— V8 缺字段负向对照的快照夹具（库不动，只改快照 JSON）

missing_subfield/  run2_summary.json 删掉 source_stat.touched            → 期望 V8 FAIL、EXIT 1
missing_key/       run1_summary.json 整个 dry_run 键删除                  → 期望 V8 FAIL、EXIT 1（不得抛 KeyError）

两份目录里的 run1/run2 摘要均由 ops/reports/r1_2/ 原样复制后只做上述一处删改；
stage3_excluded_rows.csv 也一并复制，保证 V13 仍能读到留痕（避免因文件缺失而误判）。

执行命令与输出见上一级 r1_2/10_negctl_missing_subfield.log、r1_2/11_negctl_missing_key.log。
