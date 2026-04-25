#!/bin/bash
# Database Management Script
# Utilities for PostgreSQL database management

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DB_NAME="image_search"
DB_USER="postgres"
DB_HOST="localhost"
DB_PORT="5432"

echo -e "${GREEN}🗄️  PostgreSQL Database Management${NC}\n"

# Function: Create database
create_db() {
    echo -e "${YELLOW}Creating database: $DB_NAME${NC}"
    createdb -h $DB_HOST -U $DB_USER $DB_NAME 2>/dev/null && \
    echo -e "${GREEN}✓ Database created${NC}" || \
    echo -e "${RED}✗ Database already exists or error occurred${NC}"
}

# Function: Drop database
drop_db() {
    echo -e "${YELLOW}Dropping database: $DB_NAME${NC}"
    read -p "Are you sure? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        dropdb -h $DB_HOST -U $DB_USER $DB_NAME 2>/dev/null && \
        echo -e "${GREEN}✓ Database dropped${NC}" || \
        echo -e "${RED}✗ Error dropping database${NC}"
    fi
}

# Function: Backup database
backup_db() {
    BACKUP_FILE="backup_${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql"
    echo -e "${YELLOW}Backing up database to: $BACKUP_FILE${NC}"
    pg_dump -h $DB_HOST -U $DB_USER $DB_NAME > $BACKUP_FILE && \
    echo -e "${GREEN}✓ Backup created: $BACKUP_FILE${NC}" || \
    echo -e "${RED}✗ Backup failed${NC}"
}

# Function: Restore database
restore_db() {
    if [ -z "$1" ]; then
        echo -e "${RED}✗ Please provide backup file: $0 restore <file.sql>${NC}"
        return 1
    fi
    
    if [ ! -f "$1" ]; then
        echo -e "${RED}✗ File not found: $1${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}Restoring from: $1${NC}"
    read -p "This will overwrite existing data. Continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        psql -h $DB_HOST -U $DB_USER $DB_NAME < $1 && \
        echo -e "${GREEN}✓ Database restored${NC}" || \
        echo -e "${RED}✗ Restore failed${NC}"
    fi
}

# Function: Show database size
show_size() {
    echo -e "${YELLOW}Database size:${NC}"
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c \
    "SELECT pg_size_pretty(pg_database_size('$DB_NAME')) as size;"
}

# Function: Show table info
show_tables() {
    echo -e "${YELLOW}Tables and row counts:${NC}"
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c \
    "SELECT 
        tablename as table_name,
        (SELECT COUNT(*) FROM ONLY \"$DB_NAME\".pg_class pc, 
         information_schema.tables ist 
         WHERE pc.relname = ist.table_name 
         AND ist.table_name = t.tablename) as row_count
    FROM pg_tables t 
    WHERE schemaname = 'public';"
}

# Function: Vacuum and analyze
vacuum_db() {
    echo -e "${YELLOW}Vacuuming and analyzing database...${NC}"
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "VACUUM ANALYZE;" && \
    echo -e "${GREEN}✓ Vacuum and analyze complete${NC}" || \
    echo -e "${RED}✗ Vacuum failed${NC}"
}

# Main menu
case "$1" in
    create)
        create_db
        ;;
    drop)
        drop_db
        ;;
    backup)
        backup_db
        ;;
    restore)
        restore_db "$2"
        ;;
    size)
        show_size
        ;;
    tables)
        show_tables
        ;;
    vacuum)
        vacuum_db
        ;;
    *)
        echo "PostgreSQL Database Management Utility"
        echo ""
        echo "Usage: $0 {command} [options]"
        echo ""
        echo "Commands:"
        echo "  create              Create new database"
        echo "  drop                Drop existing database"
        echo "  backup              Backup database to SQL file"
        echo "  restore <file>      Restore database from SQL file"
        echo "  size                Show database size"
        echo "  tables              Show table info and row counts"
        echo "  vacuum              Vacuum and analyze database"
        echo ""
        echo "Examples:"
        echo "  $0 create"
        echo "  $0 backup"
        echo "  $0 restore backup_image_search_20240101_120000.sql"
        ;;
esac
