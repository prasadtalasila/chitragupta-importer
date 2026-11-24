-- CREATE TABLE statements from Zotero's public userdata schema (version 121),
-- limited to the tables the importer reads. Schema only, no library data.
CREATE TABLE version (schema TEXT PRIMARY KEY, version INT NOT NULL);
CREATE TABLE libraries (libraryID INTEGER PRIMARY KEY, type TEXT NOT NULL, editable INT NOT NULL, filesEditable INT NOT NULL, version INT NOT NULL DEFAULT 0, storageVersion INT NOT NULL DEFAULT 0, lastSync INT NOT NULL DEFAULT 0, archived INT NOT NULL DEFAULT 0);
CREATE TABLE groups (groupID INTEGER PRIMARY KEY, libraryID INT NOT NULL UNIQUE, name TEXT NOT NULL, description TEXT NOT NULL, version INT NOT NULL);
CREATE TABLE items (itemID INTEGER PRIMARY KEY, itemTypeID INT NOT NULL, dateAdded, dateModified, clientDateModified TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, libraryID INT NOT NULL, key TEXT NOT NULL, version INT NOT NULL DEFAULT 0, synced INT NOT NULL DEFAULT 0, UNIQUE(libraryID, key));
CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT, templateItemTypeID INT, display INT DEFAULT 1);
CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY, dateDeleted DEFAULT CURRENT_TIMESTAMP NOT NULL);
CREATE TABLE itemData (itemID INT, fieldID INT, valueID, PRIMARY KEY (itemID, fieldID));
CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT, fieldFormatID INT);
CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value UNIQUE);
CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT, fieldMode INT, UNIQUE (lastName, firstName, fieldMode));
CREATE TABLE itemCreators (itemID INT NOT NULL, creatorID INT NOT NULL, creatorTypeID INT NOT NULL DEFAULT 1, orderIndex INT NOT NULL DEFAULT 0, PRIMARY KEY (itemID, creatorID, creatorTypeID, orderIndex), UNIQUE (itemID, orderIndex));
CREATE TABLE creatorTypes (creatorTypeID INTEGER PRIMARY KEY, creatorType TEXT);
CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, parentItemID INT, linkMode INT, contentType TEXT, charsetID INT, path TEXT, syncState INT DEFAULT 0, storageModTime INT, storageHash TEXT, lastProcessedModificationTime INT);
CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, collectionName TEXT NOT NULL, parentCollectionID INT DEFAULT NULL, clientDateModified TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, libraryID INT NOT NULL, key TEXT NOT NULL, version INT NOT NULL DEFAULT 0, synced INT NOT NULL DEFAULT 0, UNIQUE(libraryID, key));
CREATE TABLE collectionItems (collectionID INT NOT NULL, itemID INT NOT NULL, orderIndex INT NOT NULL DEFAULT 0, PRIMARY KEY (collectionID, itemID));
CREATE TABLE deletedCollections (collectionID INTEGER PRIMARY KEY, dateDeleted DEFAULT CURRENT_TIMESTAMP NOT NULL);
CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE itemTags (itemID INT NOT NULL, tagID INT NOT NULL, type INT NOT NULL, PRIMARY KEY (itemID, tagID));
CREATE TABLE relationPredicates (predicateID INTEGER PRIMARY KEY, predicate TEXT UNIQUE);
CREATE TABLE itemRelations (itemID INT NOT NULL, predicateID INT NOT NULL, object TEXT NOT NULL, PRIMARY KEY (itemID, predicateID, object));
