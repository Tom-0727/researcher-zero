整体来讲，ResearcherZero的进行学习时的运转设计是：Plan&Execute + React
- Plan&Execute：ResearcherZero接收到学习任务，进行拆解，变成更独立，具体，简单的小任务，比如输入是“接下来请学习 Agent Memory 的 Benchmarks”，它可能拆解成 [1. 搜索 Agent Memory Benchmark，并找到最相关的5篇论文；2. 根据搜索结果继续安排学习计划]。然后直接进行 Execute，按照解析后的 Plan 顺序执行。
- React：上一步Execute进入第一个Step，然后进行React式地执行，经过多轮搜索后找齐了5篇论文，这时候会发现第二步是需要第一步信息的，怎么办？这时候就要他具有规划能力，它根据情况将计划改写成 [1. …, 2. 阅读xxx，3. 阅读yyy, …]，然后继续下一个Step的React。
这里我做了一个比较有意思的设计，就是每个React得到结束标志时，会触发一次总结，然后将这个React的对话全部压缩成一个message，形成一种上下文动态压缩的机制

