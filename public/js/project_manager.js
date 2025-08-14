/**
 * 项目管理模块
 */
export class ProjectManager {
    constructor() {
        this.currentProject = null;
        this.projects = new Map();
        this.projectSelectors = new Map();

        this.selectorConfigs = [
            { id: 'unstarted-projects', status: 'unstarted', label: 'Unstarted' },
            { id: 'in-progress-projects', status: 'in_progress', label: 'In Progress' },
            { id: 'completed-projects', status: 'completed', label: 'Completed' },
            { id: 'reviewed-projects', status: 'reviewed', label: 'Reviewed' }
        ];
    }

    async init() {
        this.initSelectors();
        this.initEventListeners();
        await this.loadProjects();
    }

    initSelectors() {
        this.selectorConfigs.forEach(config => {
            const selector = document.getElementById(config.id);
            if (selector) {
                this.projectSelectors.set(config.status, selector);
                const defaultOption = selector.querySelector('option[value=""]');
                if (defaultOption) {
                    defaultOption.textContent = config.label;
                }
            }
        });
    }

    initEventListeners() {
        this.projectSelectors.forEach((selector, status) => {
            selector.addEventListener('change', (e) => {
                this.onProjectSelect(e.target.value, status);
            });
        });

        const reloadBtn = document.getElementById('btn-reload-scene-list');
        if (reloadBtn) {
            reloadBtn.addEventListener('click', () => {
                this.loadProjects();
            });
        }
    }

    async loadProjects() {
        try {
            console.log('Loading projects...');
            this.clearAllSelectors();

            for (const config of this.selectorConfigs) {
                await this.loadProjectsByStatus(config.status);
            }

            console.log('Projects loaded successfully');
        } catch (error) {
            console.error('Failed to load projects:', error);
            this.showError('Failed to load projects: ' + error.message);
        }
    }

    async loadProjectsByStatus(status) {
        try {
            const response = await fetch(`/api/projects/list_projects?status_filter=${status}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const projects = await response.json();
            this.projects.set(status, projects);
            this.updateSelector(status, projects);

        } catch (error) {
            console.error(`Failed to load projects for status ${status}:`, error);
            throw error;
        }
    }

    updateSelector(status, projects) {
        const selector = this.projectSelectors.get(status);
        if (!selector) return;

        const defaultOption = selector.querySelector('option[value=""]');
        selector.innerHTML = '';
        if (defaultOption) {
            selector.appendChild(defaultOption);
        }

        projects.forEach(project => {
            const option = document.createElement('option');
            option.value = project.id;
            option.textContent = `${project.name}`; // removed frame_count
            option.dataset.projectData = JSON.stringify(project);
            selector.appendChild(option);
        });

        const config = this.selectorConfigs.find(c => c.status === status);
        if (config && defaultOption) {
            defaultOption.textContent = `${config.label} (${projects.length})`;
        }
    }

    clearAllSelectors() {
        this.projectSelectors.forEach((selector, status) => {
            const config = this.selectorConfigs.find(c => c.status === status);
            const defaultOption = selector.querySelector('option[value=""]');

            selector.innerHTML = '';

            if (defaultOption) {
                defaultOption.textContent = config ? config.label : status;
                selector.appendChild(defaultOption);
            } else {
                const newDefaultOption = document.createElement('option');
                newDefaultOption.value = '';
                newDefaultOption.textContent = config ? config.label : status;
                selector.appendChild(newDefaultOption);
            }
        });
    }

    async onProjectSelect(projectId, status) {
        if (!projectId) {
            this.currentProject = null;
            this.clearOtherSelectors(status);
            this.notifyProjectChange(null);
            return;
        }

        try {
            this.clearOtherSelectors(status);
            const project = await this.getProjectDetails(projectId);
            this.currentProject = project;

            console.log('Selected project:', project);
            this.notifyProjectChange(project);

        } catch (error) {
            console.error('Failed to select project:', error);
            this.showError('Failed to load project: ' + error.message);
        }
    }

    clearOtherSelectors(exceptStatus) {
        this.projectSelectors.forEach((selector, status) => {
            if (status !== exceptStatus) {
                selector.value = '';
            }
        });
    }

    async getProjectDetails(projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Failed to get project details:', error);
            throw error;
        }
    }

    async getProjectFrames(projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}/frames`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Failed to get project frames:', error);
            throw error;
        }
    }

    notifyProjectChange(project) {
        const event = new CustomEvent('projectChanged', {
            detail: { project, projectManager: this }
        });
        document.dispatchEvent(event);
    }

    showError(message) {
        console.error(message);
        alert(message);
    }

    getCurrentProject() {
        return this.currentProject;
    }

    async refreshProjects() {
        await this.loadProjects();
    }
}