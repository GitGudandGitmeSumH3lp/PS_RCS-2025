// static/js/datatable.js
document.addEventListener('DOMContentLoaded', function () {
    // --- Initialize Parcel Database DataTable ---
    if (document.getElementById('parcels-table')) {
        // Use jQuery for DataTables
        $('#parcels-table').DataTable({
            processing: true, // Show processing indicator
            serverSide: true, // Enable server-side processing
            ajax: {
                url: '/api/parcels', // Your Flask API endpoint
                type: 'GET',
                // DataTables will automatically send the required query parameters
                dataSrc: function(json) {
                    // Optional: Modify the data before it's used by DataTables
                    // json.data is the array of records
                    // Handle potential error from backend
                    if (json.error) {
                        console.error("Server error:", json.error);
                        // alert("Error loading data: " + json.error); // Or update UI
                        // Return empty array to prevent table from breaking
                        return [];
                    }
                    return json.data;
                }
            },
            columns: [
                { data: 'id' },
                { data: 'tracking_no' },
                { data: 'zone' },
                { data: 'status' },
                {
                    data: 'time_processed',
                    render: function(data, type, row) {
                        // Format the datetime for display
                        if (data) {
                            try {
                                // Use JavaScript Date object to format
                                const date = new Date(data);
                                // Example format: YYYY-MM-DD HH:MM:SS
                                // .toLocaleString() uses user's locale, you can specify options for fixed format
                                return date.toLocaleString(undefined, {
                                    year: 'numeric', month: 'short', day: 'numeric',
                                    hour: '2-digit', minute: '2-digit'
                                });
                            } catch (e) {
                                console.error("Error formatting date:", e);
                                return data; // Fallback to raw data if parsing fails
                            }
                        }
                        return 'N/A';
                    }
                },
                {
                    data: null, // We don't get a specific 'actions' field from the backend
                    orderable: false, // Disable sorting for this column
                    searchable: false, // Disable searching for this column
                    render: function(data, type, row) {
                        // Render a button that could trigger a modal or other action
                        // We pass the row data using a data attribute or directly
                        return `<button type="button" class="px-3 py-1 text-xs rounded bg-cyan-500/20 hover:bg-cyan-500/40 text-cyan-300 transition view-details-btn" onclick="showParcelModal(${row.id})">View</button>`;
                        // Example for a simple action: return `<button onclick="alert('Action for ID: ${row.id}')">Action</button>`;
                    }
                }
            ],
            order: [[0, 'desc']], // Default sort by ID descending (newest first)
            pageLength: 10, // Default number of rows per page
            lengthChange: false, // Disable page length change dropdown
            searching: false, // Disable default search, we'll use our custom one
            responsive: true, // Enable responsive behavior
            language: {
                 processing: `
                    <div class="flex justify-center py-4">
                        <div class="w-5 h-5 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
                    </div>
                 `,
                 emptyTable: "No parcels found in the database.",
                 zeroRecords: "No matching parcels found.",
                 info: "Showing _START_ to _END_ of _TOTAL_ parcels",
                 infoEmpty: "Showing 0 to 0 of 0 parcels",
                 infoFiltered: "(filtered from _MAX_ total parcels)",
                 paginate: {
                     previous: "&laquo;",
                     next: "&raquo;"
                 }
            },
            dom: '<"flex items-center justify-between mb-4"<"text-sm text-slate-400"i><"#parcels-table-pagination">>rt<"flex items-center justify-between mt-4"<"text-sm text-slate-400"l><"parcels-pagination"p>>', // Custom layout
            // Callback for when the table is fully drawn
            drawCallback: function(settings) {
                // If you need to re-attach event listeners or do something after redraw
                // console.log("Table redrawn");
            }
        });
        // --- Custom Search Binding ---
        const searchInput = document.getElementById('parcel-search');
        const dataTable = $('#parcels-table').DataTable();
        if (searchInput) {
            searchInput.addEventListener('keyup', function() {
                dataTable.search(this.value).draw();
            });
        }
    }
    // --- Show Parcel Detail Modal (Placeholder) ---
    window.showParcelModal = function(parcelId) {
        alert(`View details for parcel ID: ${parcelId}
This would open a modal with full details and image.`);
        // TODO: Implement actual modal logic here.
        // You would fetch the specific parcel details (perhaps via another API endpoint like /api/parcel/<id>)
        // and then populate and show a modal similar to the one in the previous example.
        // Example steps:
        // 1. fetch(`/api/parcel/${parcelId}`).then(res => res.json()).then(data => { ... });
        // 2. Populate modal elements with data (e.g., document.getElementById('modalTrackingNo').textContent = data.tracking_no;)
        // 3. Set image source: document.getElementById('parcelImage').src = data.image_path;
        // 4. Show the modal using a library like Bootstrap Modal or a custom function.
    };
});