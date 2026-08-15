<template>
  <div class="cli-reference">
    <div class="cli-item" v-for="cmd in commands" :key="cmd.name">
      <code class="cli-cmd">{{ cmd.name }}</code>
      <p class="cli-desc">{{ cmd.description }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
const commands = [
  { name: 'novel-creator create --title "标题" --chapters 20', description: '创建新小说项目' },
  { name: 'novel-creator run', description: '运行完整创作流程（世界观→大纲→章节）' },
  { name: 'novel-creator resume', description: '从最近的检查点恢复创作' },
  { name: 'novel-creator web --port 8000', description: '启动 Web 仪表板' },
  { name: 'novel-creator export --format markdown', description: '导出小说为 Markdown' },
  { name: 'novel-creator list', description: '列出所有已注册的小说' },
  { name: 'novel-creator status', description: '查看当前活跃小说状态' },
]
</script>

<style scoped lang="scss">
.cli-reference {
  display: flex;
  flex-direction: column;
}

.cli-item {
  padding: var(--sp-md) 0;
  border-bottom: 1px solid var(--border-muted);
}

.cli-item:last-child {
  border-bottom: none;
}

.cli-cmd {
  display: inline-block;
  font-family: var(--font-data);
  color: var(--accent-blue);
  font-size: var(--fs-sm);
  padding: var(--sp-2xs) var(--sp-xs);
  background: var(--bg-elevated);
  border-radius: var(--radius-sm);
  margin-bottom: var(--sp-xs);
}

.cli-desc {
  color: var(--text-muted);
  font-size: var(--fs-sm);
  line-height: 1.5;
}
</style>
