import React from 'react';

class AppErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            hasError: false,
            message: ''
        };
    }

    static getDerivedStateFromError(error) {
        return {
            hasError: true,
            message: error?.message || 'Unexpected UI error'
        };
    }

    componentDidCatch(error, errorInfo) {
        console.error('AppErrorBoundary caught an error:', error, errorInfo);
    }

    handleReload = () => {
        window.location.reload();
    };

    render() {
        if (this.state.hasError) {
            return (
                <div style={{ minHeight: '100vh', padding: '2rem', color: '#f4fbff', background: '#07121b' }}>
                    <h2 style={{ marginBottom: '0.75rem' }}>UI runtime error</h2>
                    <p style={{ marginBottom: '1rem', color: '#b6cad7' }}>
                        {this.state.message}
                    </p>
                    <button
                        type="button"
                        onClick={this.handleReload}
                        style={{
                            padding: '0.65rem 1rem',
                            borderRadius: '10px',
                            border: '1px solid #2ac9a3',
                            background: '#103044',
                            color: '#e5f8ff',
                            cursor: 'pointer'
                        }}
                    >
                        Reload App
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}

export default AppErrorBoundary;
