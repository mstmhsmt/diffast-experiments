package org.refactoringminer.rm1;

import com.github.gumtreediff.actions.EditScript;
import com.github.gumtreediff.actions.EditScriptGenerator;
import com.github.gumtreediff.actions.SimplifiedChawatheScriptGenerator;
import com.github.gumtreediff.actions.model.Action;
import com.github.gumtreediff.actions.model.Update;
import com.github.gumtreediff.gen.jdt.JdtTreeGenerator;
import com.github.gumtreediff.matchers.Mapping;
import com.github.gumtreediff.matchers.Matchers;
import com.github.gumtreediff.matchers.MappingStore;
import com.github.gumtreediff.tree.Tree;
import com.github.gumtreediff.tree.TreeContext;
import com.github.gumtreediff.tree.Type;
import com.github.gumtreediff.client.Run;
import static com.github.gumtreediff.tree.TypeSet.type;
import gr.uom.java.xmi.LocationInfo.CodeElementType;
import gr.uom.java.xmi.UMLOperation;
import gr.uom.java.xmi.diff.ChangeReturnTypeRefactoring;
import gr.uom.java.xmi.diff.CodeRange;
// import org.eclipse.jdt.core.dom.ASTNode;

import java.io.*;
import java.util.*;
import java.util.regex.Matcher;

public class GumTreeDiff {
//	Logger logger = LoggerFactory.getLogger(GumTreeDiff.class);
//	private String commitURL;
//
//	public GumTreeDiff(String commitURL) {
//		this.commitURL = commitURL;
//	}

  private static final Type SINGLE_VARIABLE_DECLARATION = type("SingleVariableDeclaration");
  private static final Type VARIABLE_DECLARATION_FRAGMENT = type("VariableDeclarationFragment");
  private static final Type VARIABLE_DECLARATION_STATEMENT = type("VariableDeclarationStatement");
  private static final Type VARIABLE_DECLARATION_EXPRESSION = type("VariableDeclarationExpression");
  private static final Type METHOD_DECLARATION = type("MethodDeclaration");
  private static final Type ANONYMOUS_CLASS_DECLARATION = type("AnonymoudClassDeclaration");
  private static final Type TYPE_DECLARATION = type("TypeDeclaration");
  private static final Type INTERFACE_DECLARATION = type("InterfaceDeclaration");
  private static final Type FIELD_DECLARATION = type("FieldDeclaration");
  private static final Type PACKAGE_DECLARATION = type("PackageDeclaration");
  private static final Type ENHANCED_FOR_STATEMENT = type("EnhancedForStatement");
  private static final Type SIMPLE_NAME = type("SimpleName");
  private static final Type SIMPLE_TYPE = type("SimpleType");
  private static final Type MODIFIER = type("Modifier");
  private static final Type BLOCK = type("Block");
  private static final Type METHOD_INVOCATION = type("MethodInvocation");
  private static final Type SUPER_METHOD_INVOCATION = type("SuperMethodInvocation");
  private static final Type CLASS_INSTANCE_CREATION = type("ClassInstanceCreation");
  private static final Type PRIMITIVE_TYPE = type("PrimitiveType");
  private static final Type QUALIFIED_TYPE = type("QualifiedType");
  private static final Type WILDCARD_TYPE = type("WildcardType");
  private static final Type ARRAY_TYPE = type("ArrayType");
  private static final Type PARAMETERIZED_TYPE = type("ParameterizedType");
  private static final Type NAME_QUALIFIED_TYPE = type("NameQualifiedType");
  private static final Type VARARGS_TYPE = type("VARARGS_TYPE");
  private static final Type NUMBER_LITERAL = type("NumberLiteral");
  private static final Type STRING_LITERAL = type("StringLiteral");
  private static final Type TEXT_ELEMENT = type("TextElement");
  private static final Type TAG_ELEMENT = type("TagElement");
  private static final Type COMPILATION_UNIT = type("CompilationUnit");

  // private static final Type AST_SIMPLE_NAME = type(ASTNode.nodeClassForType(ASTNode.SIMPLE_NAME).getSimpleName());
  // private static final Type AST_SIMPLE_TYPE = type(ASTNode.nodeClassForType(ASTNode.SIMPLE_TYPE).getSimpleName());


  public enum Tool {
    REFACTORING_MINER(1), REFDIFF(2), GUMTREEDIFF(3);
    private int id;

    private Tool(int id) {
      this.id = id;
    }

    public int getId() {
      return id;
    }
  }

  public Set<RefactoringInfo>
    treeDiffFile(Map<String, String> fileContentsBefore,
                 Map<String, String> fileContentsCurrent)
    throws IOException
  {
    Set<RefactoringInfo> refactorings = new LinkedHashSet<>();

    fileContentsBefore.keySet().parallelStream()
      .filter(fileContentsCurrent::containsKey)
      .forEach(filePath -> {
          try {
            TreeContext src = new JdtTreeGenerator().generateFrom().string(fileContentsBefore.get(filePath));
            TreeContext dst = new JdtTreeGenerator().generateFrom().string(fileContentsCurrent.get(filePath));
            refactorings.addAll(treeDiffForVariableRenames(src, dst, filePath,
                                                           fileContentsBefore.get(filePath),
                                                           fileContentsCurrent.get(filePath)));
            refactorings.addAll(treeDiffForTypeChanges(src, dst, filePath,
                                                       fileContentsBefore.get(filePath),
                                                       fileContentsCurrent.get(filePath)));
          } catch (Exception e) {
            System.out.println("filePath="+filePath);
            e.printStackTrace();
          }
        });

//for (String filePath : fileContentsBefore.keySet()) {
//	if (fileContentsCurrent.containsKey(filePath)) {
//		TreeContext src = new JdtTreeGenerator().generateFromString(fileContentsBefore.get(filePath));
//		TreeContext dst = new JdtTreeGenerator().generateFromString(fileContentsCurrent.get(filePath));
//		refactorings.addAll(treeDiffForVariableRenames(src, dst, filePath, fileContentsBefore.get(filePath), fileContentsCurrent.get(filePath)));
//		refactorings.addAll(treeDiffForTypeChanges(src, dst, filePath, fileContentsBefore.get(filePath), fileContentsCurrent.get(filePath)));
//		}
//	}
    return refactorings;
  }

    public static final String systemFileSeparator = Matcher.quoteReplacement(File.separator);

  public Set<RefactoringInfo>
    treeDiffGitHubAPI(List<String> filesBefore,
                      List<String> filesCurrent,
                      File currentFolder,
                      File parentFolder)
    throws IOException
  {
    Set<RefactoringInfo> refactorings = new LinkedHashSet<RefactoringInfo>();
    for (String filePath : filesBefore) {
      if (filesCurrent.contains(filePath)) {
        File f1 = new File(parentFolder + File.separator + filePath.replaceAll("/", systemFileSeparator));
        File f2 = new File(currentFolder + File.separator + filePath.replaceAll("/", systemFileSeparator));
        TreeContext src = new JdtTreeGenerator().generateFrom().file(f1);
        TreeContext dst = new JdtTreeGenerator().generateFrom().file(f2);
        String fileContentsBefore = readFileContents(f1);
        String fileContentsCurrent = readFileContents(f2);
        refactorings.addAll(treeDiffForVariableRenames(src, dst, filePath,
                                                       fileContentsBefore, fileContentsCurrent));
        refactorings.addAll(treeDiffForTypeChanges(src, dst, filePath,
                                                   fileContentsBefore, fileContentsCurrent));
      }
    }
    return refactorings;
  }

    private String readFileContents(File file) {
        try {
            InputStream in = new FileInputStream(file);
            InputStreamReader isr = new InputStreamReader(in);
            StringWriter sw = new StringWriter();
            int DEFAULT_BUFFER_SIZE = 1024 * 4;
            char[] buffer = new char[DEFAULT_BUFFER_SIZE];
            int n = 0;
            while (-1 != (n = isr.read(buffer))) {
                sw.write(buffer, 0, n);
            }
            isr.close();
            return sw.toString();
        } catch (IOException e) {
            e.printStackTrace();
        }
        return "";
    }


  private Set<RefactoringInfo>
    treeDiffForTypeChanges(TreeContext src,
                           TreeContext dst,
                           String filePath,
                           String fileContentsBefore,
                           String fileContentsCurrent)
  {
    Run.initGenerators();
    Run.initMatchers();
    Set<RefactoringInfo> refactorings = new LinkedHashSet<RefactoringInfo>();
    com.github.gumtreediff.matchers.Matcher m = Matchers.getInstance().getMatcher();
    EditScriptGenerator g = new SimplifiedChawatheScriptGenerator();
    MappingStore mappings = m.match(src.getRoot(), dst.getRoot());
    EditScript actions = g.computeActions(mappings);
    Map<String, List<Action>> actionCountMap = new LinkedHashMap<String, List<Action>>();
    for (Action action : actions) {
      String actionName = action.getName();
      String actionAsString = actionToString(action);
      Tree node = action.getNode();
      Type nodeType = node.getType();
      if ((actionName.equals("update-node") || actionName.equals("move-tree"))
          // && isTypeNode(src, node)
          && (isTypeNode(src, node) || nodeType.equals(SIMPLE_NAME))
          ) {

        System.out.println("[" + node.getType() + "][" + node.getParent().getType() + "] " + actionAsString);

        if (actionCountMap.containsKey(actionAsString)) {
          actionCountMap.get(actionAsString).add(action);
        } else {
          List<Action> renameActions = new ArrayList<Action>();
          renameActions.add(action);
          actionCountMap.put(actionAsString, renameActions);
        }
      }
    }

    for (Mapping map : mappings) {
      Tree n1 = map.first;
      Tree n2 = map.second;
      if (n1.getType().equals(PARAMETERIZED_TYPE) &&
          n2.getType().equals(PARAMETERIZED_TYPE) &&
          !isTypeNode(src, n1.getParent()) &&
          !isTypeNode(dst, n2.getParent()) &&
          !n1.isIsomorphicTo(n2)
          ) {
        if (n1.getLabel().equals("")) {
          n1.setLabel(getLabel(n1, fileContentsBefore));
        }
        Action upd = new Update(n1, getLabel(n2, fileContentsCurrent));
        String updAsString = actionToString(upd);

        System.out.println("quasi-update found: " + updAsString + "\n");

        if (actionCountMap.containsKey(updAsString)) {
          actionCountMap.get(updAsString).add(upd);
        } else {
          List<Action> acts = new ArrayList<Action>();
          acts.add(upd);
          actionCountMap.put(updAsString, acts);
        }
      }
    }

    if (actionCountMap.size() > 0)
      System.out.println();

    for (String key : actionCountMap.keySet()) {
      System.out.println("[TC] key: " + key + "\n");
      List<Action> renameActions = actionCountMap.get(key);
      for (Action action : renameActions) {
        Tree actionNode = action.getNode();
        Tree actionParent = actionNode.getParent();
        Tree actionGrandParent = actionParent.getParent();
        Tree variableT2 = findMapping(mappings, actionNode);
        Tree variableT2Parent = variableT2.getParent();
        Tree variableT2GrandParent = variableT2Parent.getParent();
        RefactoringInfo refactoring = null;

        if (isTypeNode(src, actionParent)) {
          System.out.println("actionParent is TypeNode!");

          if (actionNode.getType().equals(SIMPLE_NAME) &&
              getLabel(actionNode, fileContentsBefore).equals(getLabel(actionParent, fileContentsBefore))
              ) {
            System.out.println(actionNode.getType() + " -> " + actionParent.getType());
            actionNode = actionParent;
            actionParent = actionGrandParent;
            actionGrandParent = actionParent.getParent();
          }

          Tree pt = findParentType(src, actionParent);

          if (pt != null) {
            System.out.println(actionNode.getType() + " -> " + pt.getType());
            actionNode = pt;
            actionParent = actionNode.getParent();
            actionGrandParent = actionParent.getParent();
          }
        }
        if (isTypeNode(dst, variableT2Parent)) {
          System.out.println("variableT2Parent is TypeNode!");

          if (variableT2.getType().equals(SIMPLE_NAME) &&
              getLabel(variableT2, fileContentsCurrent).equals(getLabel(variableT2Parent, fileContentsCurrent))
              ) {
            System.out.println(variableT2.getType() + " -> " + variableT2Parent.getType());
            variableT2 = variableT2Parent;
            variableT2Parent = variableT2GrandParent;
            variableT2GrandParent = variableT2Parent.getParent();
          }

          Tree pt = findParentType(dst, variableT2Parent);

          if (pt != null) {
            System.out.println(variableT2.getType() + " -> " + pt.getType());
            variableT2 = pt;
            variableT2Parent = variableT2.getParent();
            variableT2GrandParent = variableT2Parent.getParent();
          }
        }

        System.out.println("[TC] actionNode: " + actionNode.getType() + " " +
                           getLabel(actionNode, fileContentsBefore));
        System.out.println("[TC] actionParent: " + actionParent.getType() + " "
                           + getLabel(actionParent, fileContentsBefore));
        System.out.println("[TC] actionGrandParent: " + actionGrandParent.getType() + " "
                           + getLabel(actionGrandParent, fileContentsBefore));
        System.out.println("[TC] variableT2: " +
                           variableT2.getType() + " "
                           + getLabel(variableT2, fileContentsCurrent));
        System.out.println("[TC] variableT2Parent: " +
                           variableT2Parent.getType() + " "
                           + getLabel(variableT2Parent, fileContentsCurrent));
        System.out.println("[TC] variableT2GrandParent: " +
                           variableT2GrandParent.getType() + " "
                           + getLabel(variableT2GrandParent, fileContentsCurrent));
        System.out.println("[TC] renameActions: " + renameActions.size() + "\n");

        if (action.getName().equals("move-tree") && actionNode.isIsomorphicTo(variableT2)) {
          System.out.println("actionNode is isomorphic to variableT2!\n");
          continue;
        }

        CodeRange left = createCodeRange(actionNode, filePath, fileContentsBefore, CodeElementType.TYPE);
        CodeRange right = createCodeRange(variableT2, filePath, fileContentsCurrent, CodeElementType.TYPE);

        if (actionParent.getType().equals(SINGLE_VARIABLE_DECLARATION) &&
            actionGrandParent.getType().equals(METHOD_DECLARATION) &&
            variableT2GrandParent.getType().equals(METHOD_DECLARATION)) {
          String v1 = generateVariableSignature(src, actionParent, fileContentsBefore);
          String v2 = generateVariableSignature(dst, variableT2Parent, fileContentsCurrent);
          String signature = generateMethodSignature(dst, variableT2GrandParent, fileContentsCurrent);
          String className = generateClassSignature(dst, variableT2GrandParent.getParent());
          left.setDescription("original variable declaration").setCodeElement(v1);
          right.setDescription("changed-type variable declaration").setCodeElement(v2);
          String description =
            "Change Parameter Type " + v1 + " to " + v2 + " in method " + signature + " in class " + className;
          refactoring = new RefactoringInfo(description, left, right);

        } else if (actionParent.getType().equals(FIELD_DECLARATION)) {
          String t1 = actionNode.getLabel();
          String t2 = variableT2.getLabel();
          String v1 = null;
          for (Tree child : actionParent.getChildren()) {
            if (child.getType().equals(VARIABLE_DECLARATION_FRAGMENT)) {
              v1 = generateVariableSignature(src, child, fileContentsBefore);
              break;
            }
          }
          String v2 = null;
          for (Tree child : variableT2Parent.getChildren()) {
            if (child.getType().equals(VARIABLE_DECLARATION_FRAGMENT)) {
              v2 = generateVariableSignature(dst, child, fileContentsCurrent);
              break;
            }
          }
          String className = generateClassSignature(dst, variableT2Parent.getParent());
          if (v1 != null && v2 != null) {
            left.setDescription("original attribute declaration").setCodeElement(v1);
            right.setDescription("changed-type attribute declaration").setCodeElement(v2);
            String description = "Change Attribute Type " + v1 + " to " + v2 + " in class " + className;
            refactoring = new RefactoringInfo(description, left, right);
          }
        } else if (actionParent.getType().equals(VARIABLE_DECLARATION_STATEMENT) ||
                   actionParent.getType().equals(VARIABLE_DECLARATION_EXPRESSION)) {
          String t1 = actionNode.getLabel();
          String t2 = variableT2.getLabel();
          String v1 = null;
          for (Tree child : actionParent.getChildren()) {
            if (child.getType().equals(VARIABLE_DECLARATION_FRAGMENT)) {
              v1 = generateVariableSignature(src, child, fileContentsBefore);
              break;
            }
          }
          String v2 = null;
          for (Tree child : variableT2Parent.getChildren()) {
            if (child.getType().equals(VARIABLE_DECLARATION_FRAGMENT)) {
              v2 = generateVariableSignature(dst, child, fileContentsCurrent);
              break;
            }
          }
          Tree parentMethodDeclaration = findParentMethodDeclaration(dst, variableT2Parent);
          Tree parentTypeDeclaration;
          if (parentMethodDeclaration == null) {
            parentTypeDeclaration = findParentTypeDeclaration(dst, variableT2Parent);
          } else {
            parentTypeDeclaration = parentMethodDeclaration.getParent();
          }
          String signature = generateMethodSignature(dst, parentMethodDeclaration, fileContentsCurrent);
          String className = generateClassSignature(dst, parentTypeDeclaration);
          if (v1 != null && v2 != null) {
            left.setDescription("original variable declaration").setCodeElement(v1);
            right.setDescription("changed-type variable declaration").setCodeElement(v2);
            String description =
              "Change Variable Type " + v1 + " to " + v2 + " in method " + signature + " in class " + className;
            refactoring = new RefactoringInfo(description, left, right);
          }
        } else if (actionParent.getType().equals(SINGLE_VARIABLE_DECLARATION) &&
                   actionGrandParent.getType().equals(ENHANCED_FOR_STATEMENT)) {
          String v1 = generateVariableSignature(src, actionParent, fileContentsBefore);
          String v2 = generateVariableSignature(dst, variableT2Parent, fileContentsCurrent);
          Tree parentMethodDeclaration = findParentMethodDeclaration(dst, variableT2Parent);
          Tree parentTypeDeclaration;
          if (parentMethodDeclaration == null) {
            parentTypeDeclaration = findParentTypeDeclaration(dst, variableT2Parent);
          } else {
            parentTypeDeclaration = parentMethodDeclaration.getParent();
          }
          String signature = generateMethodSignature(dst, parentMethodDeclaration, fileContentsCurrent);
          String className = generateClassSignature(dst, parentTypeDeclaration);
          left.setDescription("original variable declaration").setCodeElement(v1);
          right.setDescription("changed-type variable declaration").setCodeElement(v2);
          String description =
            "Change Variable Type " + v1 + " to " + v2 + " in method " + signature + " in class " + className;
          refactoring = new RefactoringInfo(description, left, right);

        } else if (actionParent.getType().equals(METHOD_DECLARATION)) {
          String t1 = getLabel(actionNode, fileContentsBefore);
          String t2 = getLabel(variableT2, fileContentsCurrent);
          Tree parentMethodDeclaration = findParentMethodDeclaration(dst, variableT2);
          if (parentMethodDeclaration != null) {
            String signature = generateMethodSignature(dst, parentMethodDeclaration, fileContentsCurrent);
            String className = generateClassSignature(dst, parentMethodDeclaration.getParent());
            left.setDescription("original return type").setCodeElement(t1);
            right.setDescription("changed return type").setCodeElement(t2);
            String description =
              "Change Return Type " + t1 + " to " + t2 + " in method " + signature + " in class " + className;
            if (signature.endsWith(t2)) {
              refactoring = new RefactoringInfo(description, left, right);
            }
          }
        }
        if (refactoring != null) {
          System.out.println("type-change detected: " + refactoring.getDescription() + "\n");
          refactorings.add(refactoring);
        }
      }
    }
    return refactorings;
  }

    private CodeRange createCodeRange(Tree node, String filePath, String fileContent, CodeElementType type) {
        int startOffset = node.getPos();
        int endOffset = node.getEndPos();
        String linesBeforeAndIncludingOffset = fileContent.substring(0, startOffset - 1);
        int startLine = getLines(linesBeforeAndIncludingOffset).length;
        int startColumn = startOffset - getNumberOfCharsForLines(linesBeforeAndIncludingOffset, startLine - 1);

        linesBeforeAndIncludingOffset = fileContent.substring(0, endOffset - 1);
        int endLine = getLines(linesBeforeAndIncludingOffset).length;
        int endColumn = endOffset - getNumberOfCharsForLines(linesBeforeAndIncludingOffset, endLine - 1);
        return new CodeRange(filePath, startLine, endLine, startColumn, endColumn, type);
    }

    private String[] getLines(String string) {
        if (string.indexOf("\n") >= 0) {
            return string.split("\n");
        } else if (string.indexOf("\r") >= 0) {
            return string.split("\r");
        }
        return new String[]{string};
    }

    private int getNumberOfCharsForLines(String fileContents, int line) {
        int charsBeforeLine = 0;
        String[] lines = getLines(fileContents);
        for (int i = 0; i < line && i < lines.length; i++) {
            charsBeforeLine += lines[i].length() + 1; // 1 for Line Feed character
        }
        // Happens when the last char of the document is not a line feed character
        if (charsBeforeLine > fileContents.length() - 1) {
            charsBeforeLine = fileContents.length() - 1;
        }
        return charsBeforeLine;
    }

  private String actionToString(Action action) {
    Tree node = action.getNode();
    String s;
    try {
      s = action.getName() + " from " + node.getLabel() + " to " + ((Update)action).getValue();
    } catch (Exception e) {
      s = action.getName();
    }
    return s;
  }

  private Set<RefactoringInfo>
    treeDiffForVariableRenames(TreeContext src,
                               TreeContext dst,
                               String filePath,
                               String fileContentsBefore,
                               String fileContentsCurrent)
  {
    Run.initGenerators();
    Run.initMatchers();
    Set<RefactoringInfo> refactorings = new LinkedHashSet<RefactoringInfo>();
    com.github.gumtreediff.matchers.Matcher m = Matchers.getInstance().getMatcher();
    EditScriptGenerator g = new SimplifiedChawatheScriptGenerator();
    MappingStore mappings = m.match(src.getRoot(), dst.getRoot());
    EditScript actions = g.computeActions(mappings);
    Map<String, List<Action>> actionCountMap = new LinkedHashMap<String, List<Action>>();
    for (Action action : actions) {
      String actionAsString = actionToString(action);
      Tree node = action.getNode();
      Type nodeType = node.getType();
      Tree parent = node.getParent();
      Type parentType = parent.getType();
      if (action.getName().equals("update-node")
          && !nodeType.equals(STRING_LITERAL)
          && !nodeType.equals(NUMBER_LITERAL)
          && !nodeType.equals(TEXT_ELEMENT)
          && !parentType.equals(TAG_ELEMENT)
          // && node.getType().equals(AST_SIMPLE_NAME)
          // && parent.getType().equals(AST_SIMPLE_TYPE)
          // && !src.getTypeLabel(parent).equals(METHOD_DECLARATION)
          ) {

        System.out.println("[" + node.getType() + "][" + parent.getType() + "] " + actionAsString);

        if (actionCountMap.containsKey(actionAsString)) {
          actionCountMap.get(actionAsString).add(action);
        } else {
          List<Action> renameActions = new ArrayList<Action>();
          renameActions.add(action);
          actionCountMap.put(actionAsString, renameActions);
        }
      }
    }
    if (actionCountMap.size() > 0)
      System.out.println();

    for (String key : actionCountMap.keySet()) {
      System.out.println("[R] key: " + key + "\n");
      List<Action> renameActions = actionCountMap.get(key);
      for (Action action : renameActions) {
        Tree actionNode = action.getNode();
        Tree actionParent = actionNode.getParent();
        Tree actionGrandParent = actionParent.getParent();
        Tree variableT2 = findMapping(mappings, actionNode);
        Tree variableT2Parent = variableT2.getParent();
        Tree variableT2GrandParent = variableT2Parent.getParent();
        RefactoringInfo refactoring = null;

        System.out.println("[R] actionNode: " + actionNode.getType());
        System.out.println("[R] actionParent: " + actionParent.getType());
        System.out.println("[R] actionGrandParent: " + actionGrandParent.getType());
        System.out.println("[R] variableT2GrandParent: " + variableT2GrandParent.getType());
        System.out.println("[R] renameActions: " + renameActions.size() + "\n");

        if (actionParent.getType().equals(METHOD_DECLARATION)) {
          String msOld = generateMethodSignature(src, actionParent, fileContentsBefore);
          String msNew = generateMethodSignature(dst, variableT2Parent, fileContentsCurrent);
          String classNameSrc = generateClassSignature(src, actionGrandParent);
          String classNameDst = generateClassSignature(dst, variableT2GrandParent);
          CodeRange left = createCodeRange(actionNode, filePath, fileContentsBefore,
                                           CodeElementType.METHOD_DECLARATION);
          CodeRange right = createCodeRange(variableT2, filePath, fileContentsCurrent,
                                            CodeElementType.METHOD_DECLARATION);
          left.setDescription("original method name").setCodeElement(actionNode.getLabel());
          right.setDescription("renamed method name").setCodeElement(variableT2.getLabel());
          String description = "Rename Method " + msOld + " renamed to " + msNew + " in class " + classNameDst;
            // classNameSrc.equals(classNameDst)
            // ? "Rename Method " + msOld + " renamed to " + msNew + " in class " + classNameDst
            // : "Move And Rename Method " + msOld + " in class " + classNameSrc + " to " + msNew + " in class " + classNameDst;
          refactoring = new RefactoringInfo(description, left, right);

        } else if (actionParent.getType().equals(SINGLE_VARIABLE_DECLARATION) &&
                   actionGrandParent.getType().equals(METHOD_DECLARATION) &&
                   variableT2GrandParent.getType().equals(METHOD_DECLARATION)) {
          String v1 = generateVariableSignature(src, actionParent, fileContentsBefore);
          String v2 = generateVariableSignature(dst, variableT2Parent, fileContentsCurrent);
          String signature = generateMethodSignature(dst, variableT2GrandParent, fileContentsCurrent);
          String className = generateClassSignature(dst, variableT2GrandParent.getParent());
          CodeRange left = createCodeRange(actionNode, filePath, fileContentsBefore,
                                           CodeElementType.SINGLE_VARIABLE_DECLARATION);
          CodeRange right = createCodeRange(variableT2, filePath, fileContentsCurrent,
                                            CodeElementType.SINGLE_VARIABLE_DECLARATION);
          left.setDescription("original variable declaration").setCodeElement(v1);
          right.setDescription("renamed variable declaration").setCodeElement(v2);
          String description =
            "Rename Parameter " + v1 + " to " + v2 + " in method " + signature + " in class " + className;
          refactoring = new RefactoringInfo(description, left, right);

        } else if (actionParent.getType().equals(VARIABLE_DECLARATION_FRAGMENT) &&
                   actionGrandParent.getType().equals(FIELD_DECLARATION) &&
                   renameActions.size() > 1) {
          String v1 = generateVariableSignature(src, actionParent, fileContentsBefore);
          String v2 = generateVariableSignature(dst, variableT2Parent, fileContentsCurrent);
          String className = generateClassSignature(dst, variableT2GrandParent.getParent());
          CodeRange left = createCodeRange(actionNode, filePath, fileContentsBefore,
                                           CodeElementType.FIELD_DECLARATION);
          CodeRange right = createCodeRange(variableT2, filePath, fileContentsCurrent,
                                            CodeElementType.FIELD_DECLARATION);
          left.setDescription("original attribute declaration").setCodeElement(v1);
          right.setDescription("renamed attribute declaration").setCodeElement(v2);
          String description = "Rename Attribute " + v1 + " to " + v2 + " in class " + className;
          refactoring = new RefactoringInfo(description, left, right);

        } else if (actionParent.getType().equals(VARIABLE_DECLARATION_FRAGMENT) &&
                   (actionGrandParent.getType().equals(VARIABLE_DECLARATION_STATEMENT) ||
                    actionGrandParent.getType().equals(VARIABLE_DECLARATION_EXPRESSION)) &&
                   renameActions.size() > 1) {
          String v1 = generateVariableSignature(src, actionParent, fileContentsBefore);
          String v2 = generateVariableSignature(dst, variableT2Parent, fileContentsCurrent);
          Tree parentMethodDeclaration = findParentMethodDeclaration(dst, variableT2Parent);
          Tree parentTypeDeclaration;
          if (parentMethodDeclaration == null) {
            parentTypeDeclaration = findParentTypeDeclaration(dst, variableT2Parent);
          } else {
            parentTypeDeclaration = parentMethodDeclaration.getParent();
          }
          String signature = generateMethodSignature(dst, parentMethodDeclaration, fileContentsCurrent);
          String className = generateClassSignature(dst, parentTypeDeclaration);
          CodeElementType type =
            actionGrandParent.getType().equals(VARIABLE_DECLARATION_STATEMENT) ?
            CodeElementType.VARIABLE_DECLARATION_STATEMENT :
            actionGrandParent.getType().equals(VARIABLE_DECLARATION_EXPRESSION) ?
            CodeElementType.VARIABLE_DECLARATION_EXPRESSION : null;
          CodeRange left = createCodeRange(actionNode, filePath, fileContentsBefore, type);
          CodeRange right = createCodeRange(variableT2, filePath, fileContentsCurrent, type);
          left.setDescription("original variable declaration").setCodeElement(v1);
          right.setDescription("renamed variable declaration").setCodeElement(v2);
          String description =
            "Rename Variable " + v1 + " to " + v2 + " in method " + signature + " in class " + className;
          refactoring = new RefactoringInfo(description, left, right);

        } else if (actionParent.getType().equals(SINGLE_VARIABLE_DECLARATION) &&
                   actionGrandParent.getType().equals(ENHANCED_FOR_STATEMENT) &&
                   renameActions.size() > 1) {
          String v1 = generateVariableSignature(src, actionParent, fileContentsBefore);
          String v2 = generateVariableSignature(dst, variableT2Parent, fileContentsCurrent);
          Tree parentMethodDeclaration = findParentMethodDeclaration(dst, variableT2Parent);
          Tree parentTypeDeclaration;
          if (parentMethodDeclaration == null) {
            parentTypeDeclaration = findParentTypeDeclaration(dst, variableT2Parent);
          } else {
            parentTypeDeclaration = parentMethodDeclaration.getParent();
          }
          String signature = generateMethodSignature(dst, parentMethodDeclaration, fileContentsCurrent);
          String className = generateClassSignature(dst, parentTypeDeclaration);
          CodeRange left = createCodeRange(actionNode, filePath, fileContentsBefore,
                                           CodeElementType.ENHANCED_FOR_STATEMENT_PARAMETER_NAME);
          CodeRange right = createCodeRange(variableT2, filePath, fileContentsCurrent,
                                            CodeElementType.ENHANCED_FOR_STATEMENT_PARAMETER_NAME);
          left.setDescription("original variable declaration").setCodeElement(v1);
          right.setDescription("renamed variable declaration").setCodeElement(v2);
          String description =
            "Rename Variable " + v1 + " to " + v2 + " in method " + signature + " in class " + className;
          refactoring = new RefactoringInfo(description, left, right);
        }
        if (refactoring != null) {
          System.out.println("rename detected: " + refactoring.getDescription() + "\n");
          refactorings.add(refactoring);
        }
      }
    }
    return refactorings;
  }

  private Tree findParentMethodDeclaration(TreeContext context, Tree node) {
    Tree parent = node.getParent();
    while (parent != null) {
      if (parent.getType().equals(METHOD_DECLARATION)) {
        return parent;
      }
      parent = parent.getParent();
    }
    return null;
  }

  private Tree findParentTypeDeclaration(TreeContext context, Tree node) {
    Tree parent = node.getParent();
    while (parent != null) {
      if (parent.getType().equals(TYPE_DECLARATION)) {
        return parent;
      }
      parent = parent.getParent();
    }
    return null;
  }

  private Tree findParentType(TreeContext context, Tree node) {
    Tree parent = node;
    while (parent != null && isTypeNode(context, parent)) {
      if ((parent.getType().equals(PARAMETERIZED_TYPE) || parent.getType().equals(ARRAY_TYPE))
          && !isTypeNode(context, parent.getParent())
          ) {
        return parent;
      }
      parent = parent.getParent();
    }
    return null;
  }

    private Tree findMapping(MappingStore mappings, Tree tree1) {
        for (Mapping mapping : mappings) {
            if (mapping.first.equals(tree1)) {
                return mapping.second;
            }
        }
        return null;
    }

  private String
    generateVariableSignature(TreeContext context,
                              Tree variableDeclaration,
                              String fileContent)
  {
    StringBuilder sb = new StringBuilder();
    if (variableDeclaration.getType().equals(SINGLE_VARIABLE_DECLARATION)) {
      String type = null;
      String name = null;
      for (Tree child : variableDeclaration.getChildren()) {
        if (isTypeNode(context, child)) {
          type = getLabel(child, fileContent);
        } else if (child.getType().equals(SIMPLE_NAME)) {
          name = child.getLabel();
        }
      }
      sb.append(name + " : " + type);
    } else if (variableDeclaration.getType().equals(VARIABLE_DECLARATION_FRAGMENT)) {
      String name = null;
      String type = null;
      for (Tree child : variableDeclaration.getChildren()) {
        if (child.getType().equals(SIMPLE_NAME)) {
          name = child.getLabel();
          break;
        }
      }
      Tree parent = variableDeclaration.getParent();
      for (Tree child : parent.getChildren()) {
        if (isTypeNode(context, child)) {
          type = getLabel(child, fileContent);
          break;
        }
      }
      sb.append(name + " : " + type);
    }
    return sb.toString();
  }

    private String generateClassSignature(TreeContext context, Tree typeDeclaration) {
        String className = null;
        Tree parent = typeDeclaration;
        while (parent != null) {
            for (Tree child : parent.getChildren()) {
                if (child.getType().equals(SIMPLE_NAME) && !isArgument(context, parent, child)) {
                    if (className == null) {
                        className = child.getLabel();
                    } else {
                        className = child.getLabel() + "." + className;
                    }
                    break;
                } else if (child.getType().equals(PACKAGE_DECLARATION)) {
                    for (Tree child2 : child.getChildren()) {
                        if (child2.getLabel().length() > 0) {
                            className = child2.getLabel() + "." + className;
                            break;
                        }
                    }
                }
            }
            parent = parent.getParent();
        }
        return className;
    }

    private boolean isArgument(TreeContext context, Tree parent, Tree child) {
        if (parent.getType().equals(METHOD_INVOCATION)) {

        } else if (parent.getType().equals(SUPER_METHOD_INVOCATION)) {

        } else if (parent.getType().equals(CLASS_INSTANCE_CREATION)) {
            boolean typeFound = false;
            boolean bodyFound = false;
            for (Tree child2 : parent.getChildren()) {
                if (isTypeNode(context, child2)) {
                    typeFound = true;
                } else if (child.getType().equals(BLOCK)) {
                    bodyFound = true;
                } else if (typeFound && !bodyFound && child2.equals(child)) {
                    return true;
                }
            }
        }
        return false;
    }

  private String
    generateMethodSignature(TreeContext context,
                            Tree methodDeclaration,
                            String fileContent)
  {
    if (methodDeclaration == null)
      return "";

    StringBuilder sb = new StringBuilder();
    List<Tree> children = methodDeclaration.getChildren();
    String returnType = null;
    boolean accessModifierFound = false;
    boolean bodyFound = false;
    for (int i = 0; i < children.size(); i++) {
      Tree child = children.get(i);
      System.out.println("generateMethodSignature: child["+i+"] "+child.getType());
      if (child.getType().equals(SIMPLE_NAME)) {
        sb.append(child.getLabel()).append("(");

      } else if (isTypeNode(context, child) && returnType == null) {
        returnType = getLabel(child, fileContent);

      } else if (child.getType().equals(MODIFIER)) {
        if (child.getLabel().equals("public") ||
            child.getLabel().equals("private") ||
            child.getLabel().equals("protected")) {
          sb.append(child.getLabel()).append(" ");
          accessModifierFound = true;
        }
        else if (child.getLabel().equals("abstract")) {
          sb.append(child.getLabel()).append(" ");
        }
        else if (child.getLabel().equals("default")) {
          sb.append("public ");
          accessModifierFound = true;
        }
      } else if (child.getType().equals(SINGLE_VARIABLE_DECLARATION)) {
        String type = "";
        String name = "";
        for (Tree child2 : child.getChildren()) {
          System.out.println("child2: " + child2.getType() + ": " + getLabel(child2, fileContent));
          if (isTypeNode(context, child2)) {
            type = getLabel(child2, fileContent);
          }
          if (child2.getType().equals(SIMPLE_NAME)) {
            name = child2.getLabel();
          }
          if (child2.getType().equals(SINGLE_VARIABLE_DECLARATION)) {
            for (Tree child3 : child2.getChildren()) {
              System.out.println("child3: " + child3.getType() + ": " + getLabel(child3, fileContent));
              if (isTypeNode(context, child3)) {
                type = getLabel(child3, fileContent);
              }
              if (child3.getType().equals(SIMPLE_NAME)) {
                name = child3.getLabel();
              }
            }
          }
        }
        System.out.println("type=" + type);
        System.out.println("name=" + name);
/*
        if (!type.endsWith("...") &&
            (name.endsWith("s") || name.endsWith("List")) && i == children.size() - 2 &&
            children.get(i + 1).getType().equals(BLOCK) &&
            !type.endsWith("[]") && !type.contains("List") && !type.contains("Collection") &&
            !type.contains("Iterable") && !type.contains("Set") && !type.contains("Iterator") &&
            !type.contains("Array") &&
            !type.endsWith("s") && !type.toLowerCase().contains(name.toLowerCase()) &&
            !name.endsWith("ss") && !type.equals("boolean") && !type.equals("int")
            ) {
          //hack for varargs
          sb.append(name + " " + type + "...");
        } else {
*/
          sb.append(name + " " + type);
//        }
        if (i < children.size() - 1 && children.get(i + 1).getType().equals(SINGLE_VARIABLE_DECLARATION)) {
          sb.append(",").append(" ");
        }
      } else if (child.getType().equals(BLOCK)) {
        bodyFound = true;
      }
    }
    sb.append(")");
    if (returnType != null) {
      sb.append(" : ").append(returnType);
    }
    if (!accessModifierFound) {
      if (bodyFound) {
        return "package " + sb.toString();
      } else {
        return "public " + sb.toString();
      }
    }
    return sb.toString();
  }

  private String getLabel(Tree node, String fileContent) {
    String type = node.getLabel();
    if (type.equals("")) {
      Type ty = node.getType();
      if (ty.equals(TYPE_DECLARATION) || ty.equals(COMPILATION_UNIT))
        type = "...";
      else
        type = fileContent.substring(node.getPos(), node.getEndPos());
    }
    return type;
  }

    private boolean isTypeNode(TreeContext context, Tree child) {
        return child.getType().equals(SIMPLE_TYPE) ||
                child.getType().equals(PRIMITIVE_TYPE) ||
                child.getType().equals(QUALIFIED_TYPE) ||
                child.getType().equals(WILDCARD_TYPE) ||
                child.getType().equals(ARRAY_TYPE) ||
                child.getType().equals(PARAMETERIZED_TYPE) ||
                child.getType().equals(VARARGS_TYPE) ||
                child.getType().equals(NAME_QUALIFIED_TYPE);
    }

    public class RefactoringInfo {
        private String description;
        private CodeRange left;
        private CodeRange right;

        public RefactoringInfo(String description, CodeRange left, CodeRange right) {
            super();
            this.description = description;
            this.left = left;
            this.right = right;
        }

        @Override
        public int hashCode() {
            final int prime = 31;
            int result = 1;
            result = prime * result + ((description == null) ? 0 : description.hashCode());
            return result;
        }

        @Override
        public boolean equals(Object obj) {
            if (this == obj)
                return true;
            if (obj == null)
                return false;
            if (getClass() != obj.getClass())
                return false;
            RefactoringInfo other = (RefactoringInfo) obj;
            if (description == null) {
                if (other.description != null)
                    return false;
            } else if (!description.equals(other.description))
                return false;
            return true;
        }

        public String getDescription() {
            return description;
        }

        public CodeRange getLeft() {
            return left;
        }

        public CodeRange getRight() {
            return right;
        }
    }


    private String generateMoveMethod(ChangeReturnTypeRefactoring r, String refactoringName) {
        StringBuilder sb = new StringBuilder();
        sb.append(refactoringName).append(" ");
        sb.append(r.getOperationBefore());
        sb.append(" in class ");
        sb.append(r.getOperationBefore().getClassName());
        sb.append(" to ");
        sb.append(r.getOperationAfter());
        sb.append(" in class ");
        sb.append(r.getOperationAfter().getClassName());
        return sb.toString();
    }

    private String generateRenameMethod(ChangeReturnTypeRefactoring r) {
        StringBuilder sb = new StringBuilder();
        sb.append("Rename Method").append(" ");
        sb.append(r.getOperationBefore());
        sb.append(" renamed to ");
        sb.append(r.getOperationAfter());
        sb.append(" in class ").append(getClassName(r.getOperationBefore(), r.getOperationAfter()));
        return sb.toString();
    }

    private String getClassName(UMLOperation originalOperation, UMLOperation renamedOperation) {
        String sourceClassName = originalOperation.getClassName();
        String targetClassName = renamedOperation.getClassName();
        boolean targetIsAnonymousInsideSource = false;
        if (targetClassName.startsWith(sourceClassName + ".")) {
            String targetClassNameSuffix = targetClassName.substring(sourceClassName.length() + 1, targetClassName.length());
            targetIsAnonymousInsideSource = isNumeric(targetClassNameSuffix);
        }
        return sourceClassName.equals(targetClassName) || targetIsAnonymousInsideSource ? sourceClassName : targetClassName;
    }

    private static boolean isNumeric(String str) {
        for (char c : str.toCharArray()) {
            if (!Character.isDigit(c)) return false;
        }
        return true;
    }

} 

