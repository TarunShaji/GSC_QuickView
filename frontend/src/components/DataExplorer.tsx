import { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';
import type { Website, Property } from '../types';
import PropertyDashboard from './PropertyDashboard';
import AlertsPage from './AlertsPage';
import SettingsPage from './SettingsPage';

export default function DataExplorer() {
    const { accountId } = useAuth();
    const [websites, setWebsites] = useState<Website[]>([]);
    const [selectedWebsite, setSelectedWebsite] = useState<Website | null>(null);
    const [properties, setProperties] = useState<Property[]>([]);
    const [selectedProperty, setSelectedProperty] = useState<Property | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'properties' | 'alerts' | 'settings'>('properties');

    // Fetch websites on mount
    useEffect(() => {
        if (!accountId) return;

        const fetchWebsites = async () => {
            try {
                setIsLoading(true);
                const data = await api.websites.getAll(accountId);
                setWebsites(data);
                // Auto-select first website if available
                if (data.length > 0) {
                    setSelectedWebsite(data[0]);
                }
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to fetch websites');
            } finally {
                setIsLoading(false);
            }
        };
        fetchWebsites();
    }, [accountId]);

    // Fetch properties when website changes
    useEffect(() => {
        if (!selectedWebsite || !accountId) {
            setProperties([]);
            setSelectedProperty(null);
            return;
        }

        const fetchProperties = async () => {
            try {
                const data = await api.websites.getProperties(accountId, selectedWebsite.id);
                setProperties(data);
                // Auto-select first property
                if (data.length > 0) {
                    setSelectedProperty(data[0]);
                }
            } catch (err) {
                console.error('Failed to fetch properties:', err);
                setProperties([]);
            }
        };
        fetchProperties();
    }, [selectedWebsite, accountId]);

    if (!accountId) return null;

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded-lg">
                {error}
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Tab Navigation */}
            <div className="border-b border-slate-700">
                <nav className="flex space-x-8">
                    <button
                        onClick={() => setActiveTab('properties')}
                        className={`pb-4 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === 'properties'
                            ? 'border-blue-500 text-blue-400'
                            : 'border-transparent text-slate-400 hover:text-slate-300'
                            }`}
                    >
                        Property Analytics
                    </button>
                    <button
                        onClick={() => setActiveTab('alerts')}
                        className={`pb-4 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === 'alerts'
                            ? 'border-blue-500 text-blue-400'
                            : 'border-transparent text-slate-400 hover:text-slate-300'
                            }`}
                    >
                        Alerts
                    </button>
                    <button
                        onClick={() => setActiveTab('settings')}
                        className={`pb-4 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === 'settings'
                            ? 'border-blue-500 text-blue-400'
                            : 'border-transparent text-slate-400 hover:text-slate-300'
                            }`}
                    >
                        Settings
                    </button>
                </nav>
            </div>

            {activeTab === 'properties' ? (
                <>
                    {/* Website & Property Selectors */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Website Selector */}
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-2">
                                Website
                            </label>
                            <select
                                value={selectedWebsite?.id || ''}
                                onChange={(e) => {
                                    const website = websites.find((w) => w.id === e.target.value);
                                    setSelectedWebsite(website || null);
                                    setSelectedProperty(null);
                                }}
                                className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            >
                                {websites.map((website) => (
                                    <option key={website.id} value={website.id}>
                                        {website.base_domain} ({website.property_count} properties)
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Property Selector */}
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-2">
                                Property
                            </label>
                            <select
                                value={selectedProperty?.id || ''}
                                onChange={(e) => {
                                    const property = properties.find((p) => p.id === e.target.value);
                                    setSelectedProperty(property || null);
                                }}
                                disabled={properties.length === 0}
                                className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
                            >
                                {properties.length === 0 ? (
                                    <option>No properties</option>
                                ) : (
                                    properties.map((property) => (
                                        <option key={property.id} value={property.id}>
                                            {property.site_url}
                                        </option>
                                    ))
                                )}
                            </select>
                        </div>
                    </div>

                    {/* Property Dashboard */}
                    {selectedProperty ? (
                        <PropertyDashboard property={selectedProperty} />
                    ) : (
                        <div className="text-center py-12 text-slate-500">
                            Select a property to view analytics
                        </div>
                    )}
                </>
            ) : activeTab === 'alerts' ? (
                <AlertsPage />
            ) : (
                <SettingsPage />
            )}
        </div>
    );
}
