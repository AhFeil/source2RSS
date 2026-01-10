root := justfile_directory()

@lack:
  echo "lack"

# === 常用配方 ===

# 创建一个空 commit ，带提交信息模板
@new:
  git commit --allow-empty --edit --file={{root}}/.gitmessage

@forget:
  if git diff --quiet HEAD HEAD~1; then \
    git reset --soft HEAD~1 && echo "✅ 空提交已删除"; \
  fi

# 将所有文件 amend
amend argument="":
  cd "{{root}}" && git add . && git commit --amend {{argument}}

# 统计代码量
cloc:
  cd {{invocation_directory()}} && git ls-files | xargs cloc


# === just 管理命令 ===

import? "justfile.local"

bashrc := "$HOME/.bashrc"
# 设置 just 的命令补全
@setup-completions:
  # 检查是否已经存在补全命令
  cmd="eval \"\$(just --justfile {{justfile()}} --completions bash)\""; \
  if ! grep -Fxq "$cmd" "{{bashrc}}"; then \
      echo '添加 just 补全到 {{bashrc}}'; \
      echo $cmd >> "{{bashrc}}"; \
  else \
      echo "补全命令已存在 {{bashrc}}，无需重复添加"; \
      echo "执行命令 source {{bashrc}} ，使之生效"; \
  fi
