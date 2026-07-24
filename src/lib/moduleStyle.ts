const MODULE_CLASS: Record<string, string> = {
  言语理解: 'mod-yuyan',
  数量关系: 'mod-shuliang',
  思维策略: 'mod-siwei',
  数学运算: 'mod-shuliang',
  图形推理: 'mod-tuxing',
  数字推理: 'mod-shuzi',
  资料分析: 'mod-ziliao',
  逻辑判断: 'mod-luoji',
  判断推理: 'mod-luoji',
  综合: 'mod-zonghe',
};

export function moduleTagClass(module: string, extra = 'tag'): string {
  const mod = MODULE_CLASS[module] || 'mod-default';
  return `${extra} ${mod}`.trim();
}
