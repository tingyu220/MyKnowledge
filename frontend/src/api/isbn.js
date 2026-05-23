import api from './index'

/**
 * 校验 ISBN 格式
 * @param {string} isbn
 * @returns {{ valid: boolean, normalized: string | null }}
 */
export const validateIsbn = (isbn) => {
  return api.post('/isbn/validate', { isbn: (isbn || '').trim() })
}
