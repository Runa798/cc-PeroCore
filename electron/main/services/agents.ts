import path from 'path'
import fs from 'fs-extra'
import { isDev, isElectron, paths } from '../utils/env'
import { logger } from '../utils/logger'

function getRootPath() {
  if (isDev && isElectron) {
    // 开发环境: dist-electron/main/services -> ProjectRoot
    return path.resolve(__dirname, '../../..')
  } else {
    return paths.resources
  }
}

/**
 * 获取 Agent 用户覆盖配置目录。
 * 用户对 Agent 的修改（启用/禁用、自定义参数等）保存在此目录，
 * 不修改源码/资源目录中的原始 config.json。
 */
function getAgentOverridesDir(): string {
  return path.join(paths.data, 'agent_overrides')
}

export async function scanLocalAgents() {
  const root = getRootPath()
  const backendAgentsDir = path.join(root, 'backend/services/mdp/agents')
  const userAgentsDir = path.join(root, 'backend/data/agents')
  // 全局配置已迁移到 paths.data
  const globalConfigPath = path.join(paths.data, 'agent_launch_config.json')
  // 兼容旧路径（如果 paths.data 中找不到，尝试旧位置）
  const legacyConfigPath = path.join(root, 'backend/data/agent_launch_config.json')

  logger.info('Main', `[Agents] 正在扫描 Agents，路径: ${backendAgentsDir}`)
  logger.info('Main', `[Agents] 全局配置路径: ${globalConfigPath}`)

  if (!(await fs.pathExists(backendAgentsDir))) {
    logger.warn('Main', `[Agents] 未找到 Agents 目录: ${backendAgentsDir}`)
    return []
  }

  // 加载全局配置
  let globalConfig = { enabled_agents: [] as string[], active_agent: '' }
  try {
    let configToLoad = globalConfigPath
    if (!(await fs.pathExists(configToLoad)) && (await fs.pathExists(legacyConfigPath))) {
      configToLoad = legacyConfigPath
      logger.info('Main', '[Agents] 从旧路径加载全局配置')
    }
    if (await fs.pathExists(configToLoad)) {
      const loadedConfig = await fs.readJson(configToLoad)
      globalConfig = { ...globalConfig, ...loadedConfig }
      logger.info('Main', `[Agents] 已加载全局配置: ${JSON.stringify(globalConfig)}`)
    } else {
      logger.info('Main', '[Agents] 全局配置未找到，使用默认值')
    }
  } catch (e) {
    logger.warn('Main', `[Agents] 加载全局 Agent 配置失败: ${e}`)
  }

  // 加载用户覆盖配置
  const overridesDir = getAgentOverridesDir()
  const loadOverride = async (agentId: string): Promise<any> => {
    const overridePath = path.join(overridesDir, `${agentId}.json`)
    if (await fs.pathExists(overridePath)) {
      try {
        return await fs.readJson(overridePath)
      } catch {
        return {}
      }
    }
    return {}
  }

  const agents = []
  // 扫描内置 + 用户 Agent 目录
  const agentDirs = [backendAgentsDir]
  if (await fs.pathExists(userAgentsDir)) {
    agentDirs.push(userAgentsDir)
    logger.info('Main', `[Agents] 同时扫描用户 Agents: ${userAgentsDir}`)
  }
  for (const scanDir of agentDirs) {
  const files = await fs.readdir(scanDir)
  for (const file of files) {
    const agentDir = path.join(scanDir, file)
    try {
      const stat = await fs.stat(agentDir)
      if (stat.isDirectory()) {
        // 检查 config.json
        const configPath = path.join(agentDir, 'config.json')
        if (await fs.pathExists(configPath)) {
          try {
            const config = await fs.readJson(configPath)
            const id = file

            // 合并用户覆盖配置
            const override = await loadOverride(id)
            const mergedConfig = { ...config, ...override }

            // 合并全局状态
            const isEnabled = globalConfig.enabled_agents.includes(id)
            const isActive = globalConfig.active_agent === id

            // 扫描头像
            let avatar = ''
            const avatarFiles = [
              'avatar.png',
              'avatar.jpg',
              'avatar.jpeg',
              'avatar.svg',
              'icon.png'
            ]
            const mimeMap: Record<string, string> = {
              '.png': 'image/png',
              '.jpg': 'image/jpeg',
              '.jpeg': 'image/jpeg',
              '.svg': 'image/svg+xml'
            }
            for (const name of avatarFiles) {
              const avatarPath = path.join(agentDir, name)
              if (await fs.pathExists(avatarPath)) {
                // 直接将文件读取为 base64 data URL，无需后端服务即可显示
                try {
                  const ext = path.extname(name).toLowerCase()
                  const mime = mimeMap[ext] || 'image/png'
                  const buf = await fs.readFile(avatarPath)
                  avatar = `data:${mime};base64,${buf.toString('base64')}`
                } catch {
                  // 回退到后端 API 路径
                  avatar = `/api/agents/${id}/avatar`
                }
                break
              }
            }

            agents.push({
              id: id,
              name: mergedConfig.name || id,
              description: mergedConfig.description || '',
              avatar: avatar || mergedConfig.avatar || '',
              path: agentDir,
              is_enabled: isEnabled,
              is_active: isActive,
              ...mergedConfig
            })
          } catch (e) {
            logger.error('Main', `无法读取 ${file} 的配置: ${e}`)
            agents.push({ id: file, name: file, description: '配置错误' })
          }
        }
      }
    } catch {
      // 忽略访问错误
    }
  }
  } // end for scanDir
  return agents
}

export async function getPlugins() {
  const root = getRootPath()
  // 后端结构: backend/nit_core/plugins
  const pluginsDir = path.join(root, 'backend/nit_core/plugins')

  logger.info('Plugin', `[插件] 正在扫描插件，路径: ${pluginsDir}`)

  if (!(await fs.pathExists(pluginsDir))) {
    logger.warn('Plugin', `[插件] 未找到目录: ${pluginsDir}`)
    return []
  }

  const plugins = []
  try {
    const files = await fs.readdir(pluginsDir)
    logger.info('Plugin', `[插件] 发现文件: ${files.join(', ')}`)

    for (const file of files) {
      // 跳过隐藏/缓存文件
      if (file.startsWith('__') || file.startsWith('.')) {
        continue
      }

      const pluginDir = path.join(pluginsDir, file)
      try {
        const stat = await fs.stat(pluginDir)
        if (stat.isDirectory()) {
          // 检查 description.json
          const descPath = path.join(pluginDir, 'description.json')
          if (await fs.pathExists(descPath)) {
            try {
              const desc = await fs.readJson(descPath)
              plugins.push({
                name: file,
                valid: true,
                ...desc
              })
              logger.info('Plugin', `[插件] 已加载 ${file}`)
            } catch (e) {
              logger.error('Plugin', `[插件] 解析 ${file} 的 description.json 失败: ${e}`)
              plugins.push({ name: file, valid: false, description: '无效配置' })
            }
          } else {
            // 猜测或列出
            logger.info('Plugin', `[插件] ${file} 缺少 description.json`)
            plugins.push({ name: file, valid: true, description: '自定义插件' })
          }
        }
      } catch (e) {
        logger.error('Plugin', `[插件] 处理 ${file} 时出错: ${e}`)
      }
    }
  } catch (e) {
    logger.error('Plugin', `[插件] 读取插件目录失败: ${e}`)
  }

  logger.info('Plugin', `[插件] 返回了 ${plugins.length} 个插件`)
  return plugins
}

export async function saveGlobalLaunchConfig(enabledAgents: string[], activeAgent: string) {
  // 保存到 paths.data（可写目录），而非 resources/backend/data（可能只读）
  const configPath = path.join(paths.data, 'agent_launch_config.json')

  logger.info('Main', `[Config] 正在保存全局配置到 ${configPath}`)
  logger.info('Main', `[Config] 数据: ${JSON.stringify({ enabledAgents, activeAgent })}`)

  try {
    await fs.ensureDir(path.dirname(configPath))

    const config = {
      enabled_agents: enabledAgents,
      active_agent: activeAgent
    }

    await fs.writeJson(configPath, config, { spaces: 4 })
    logger.info('Main', `[Config] 保存成功`)
    return config
  } catch (e) {
    logger.error('Main', `[Config] 保存全局配置失败: ${e}`)
    throw e
  }
}

export async function saveAgentLaunchConfig(agentId: string, config: any) {
  // 用户的 Agent 配置修改保存到 paths.data/agent_overrides/，不修改源码中的 config.json
  const overridesDir = getAgentOverridesDir()
  const overridePath = path.join(overridesDir, `${agentId}.json`)

  logger.info('Main', `[Config] 正在保存 Agent ${agentId} 的覆盖配置到 ${overridePath}`)

  try {
    await fs.ensureDir(overridesDir)

    // 读取已有的覆盖配置并合并
    let existing: any = {}
    if (await fs.pathExists(overridePath)) {
      existing = await fs.readJson(overridePath)
    }
    const merged = { ...existing, ...config }

    await fs.writeJson(overridePath, merged, { spaces: 4 })
    logger.info('Main', `[Config] Agent ${agentId} 覆盖配置保存成功`)
    return merged
  } catch (e) {
    logger.error('Main', `[Config] 保存 Agent ${agentId} 覆盖配置失败: ${e}`)
    throw e
  }
}
