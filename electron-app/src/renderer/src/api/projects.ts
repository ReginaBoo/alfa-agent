import api from './client'

export interface Project {
  id: number
  key: string
  name: string
  avatar_url?: string | null
  category?: string | null
  statuses?: any[]
}

export const getProjects = async (): Promise<Project[]> => {
  const response = await api.get('/jira/projects/with-statuses')

  return response.data.projects || []
}