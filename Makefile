.PHONY: setup fmt lint arch test build check card-test gates-pr
setup:  ; npm ci
fmt:    ; npx prettier --write .
lint:   ; npx prettier --check . && npx eslint . && npx tsc --noEmit
arch:   ; npx depcruise src
test:   ; npx vitest run --coverage
build:  ; npm run build
check:  lint arch test

# ---------- 入口协议块第 4 步两目标（W1-C3 / ADR-0055 决策 3） ----------
# card-test：诚实薄封装——拉卡 AC 列表+提示按 AC 先写红测试（本仓无按卡测试集
# 镜像，不假装跑过）；gates-pr：本地复现 CI 关卡（=check：lint+arch+test）+检查单。
CARD ?=
REPO ?= Cloudbird-Software/.github   # 卡所在仓（W1 波次卡都在治理仓；产品仓自有卡时 REPO=<owner>/<repo> 覆盖）

card-test: ## 读卡 AC 列表并提示测试先行：make card-test CARD=<issue#>
	@test -n "$(CARD)" || { echo "用法: make card-test CARD=<issue#>（缺 CARD）" >&2; exit 2; }
	@echo "== 卡 $(REPO)#$(CARD) 的 AC（测试先行：先按 AC 写红测试再实现）=="
	@gh issue view "$(CARD)" -R "$(REPO)" --json number,title,body \
	  --jq '"#\(.number) \(.title)\n\n\(.body)"' 2>/dev/null \
	  | awk 'NR==1{print;print ""} /^## AC/{f=1} f{print} f && /^## / && !/^## AC/{exit}' | head -60
	@echo "(空=拉取失败或卡无 AC 节——手动: gh issue view $(CARD) -R $(REPO))"

gates-pr: check ## 本地复现 CI 关卡（lint+arch+test）+ 开 PR 检查单
	@echo "== 开 PR 前检查单（机器不可判部分）：PR body 引用 ADR-NNNN（C1）/ body 带 Card: 元数据行 / 一个 PR 一件事 diff<400 行 =="
